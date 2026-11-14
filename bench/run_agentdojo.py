"""Corre AgentDojo con varias defensas (mismo modelo, misma suite, mismas tareas) y escribe results/.

Ejemplos:

    # piloto local con qwen3:8b (Ollama, sin API keys):
    python -m bench.run_agentdojo -s banking -ut user_task_0 -it injection_task_0 -d none,guard-sanitize

    # prueba de integración SIN API: el "LLM" ejecuta las llamadas de referencia de cada tarea
    python -m bench.run_agentdojo --offline -s banking -ut user_task_0 -it injection_task_0

Defensas: none, keyword, transformers_pi_detector (DeBERTa), guard-detect, guard-sanitize,
y las demás de AgentDojo (tool_filter, spotlighting_with_delimiting, repeat_user_prompt).

Cada defensa escribe results/<fecha>-<commit>-agentdojo-<suite>-<defensa>.json y una línea en
results/summary.csv (Contrato 4). Las trazas completas de AgentDojo quedan en --logdir (runs/);
si se repite un comando, AgentDojo reutiliza los casos ya corridos (no se paga dos veces).
Para forzar una ejecución limpia y reevaluar todo: use --force-rerun.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import agentdojo.logging
# Parche preventivo para bug interno de AgentDojo en NullLogger
agentdojo.logging.NullLogger.logdir = None
agentdojo.logging.NullLogger.messages = []

from agentdojo.agent_pipeline import (
    AgentPipeline,
    BasePipelineElement,
    InitQuery,
    PipelineConfig,
    SystemMessage,
    ToolsExecutionLoop,
    ToolsExecutor,
)
from agentdojo.agent_pipeline.agent_pipeline import DEFENSES, load_system_message
from agentdojo.attacks.attack_registry import load_attack
from agentdojo.attacks.base_attacks import MODEL_NAMES
from agentdojo.benchmark import benchmark_suite_with_injections, benchmark_suite_without_injections
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionsRuntime
from agentdojo.logging import OutputLogger
from agentdojo.task_suite.load_suites import get_suite
from agentdojo.types import ChatAssistantMessage, ChatMessage, text_content_block_from_string

from bench.agentdojo_guard import GuardDetect, GuardSanitize
from bench.keyword_detector import KeywordDetector

# Registro de alias para modelos locales Qwen y derivados en AgentDojo
for alias in ["qwen3-8b", "qwen3:8b", "qwen3", "qwen", "qwen2.5", "qwen2.5-7b", "local"]:
    if alias not in MODEL_NAMES:
        MODEL_NAMES[alias] = "Qwen"

RAIZ = Path(__file__).resolve().parent.parent
RESULTADOS = RAIZ / "results"
PROPIAS = ("keyword", "guard-detect", "guard-sanitize")
TODAS = ("none", "keyword", "transformers_pi_detector", "guard-detect", "guard-sanitize")
COLUMNAS = [
    "fecha", "commit", "benchmark", "suite", "version", "modelo", "ataque", "defensa", "guard_modelo",
    "n_utilidad", "utilidad", "utilidad_ic95",
    "n_ataque", "utilidad_bajo_ataque", "utilidad_bajo_ataque_ic95", "exito_ataque", "exito_ataque_ic95",
    "salidas_revisadas", "salidas_marcadas", "latencia_guard_mediana_ms", "latencia_guard_p95_ms",
    "tokens_entrada", "tokens_salida", "archivo",
]


# --- LLMs ----------------------------------------------------------------------------


class ContadorTokens:
    """Envuelve client.chat.completions.create para sumar los tokens de esta ejecución."""

    def __init__(self, client) -> None:
        self.entrada = self.salida = self.llamadas = 0
        original = client.chat.completions.create

        def create(*args, **kwargs):
            t0 = time.perf_counter()
            r = original(*args, **kwargs)
            dur = time.perf_counter() - t0
            if getattr(r, "usage", None) is not None:
                p_tok = getattr(r.usage, "prompt_tokens", 0) or 0
                c_tok = getattr(r.usage, "completion_tokens", 0) or 0
                self.entrada += p_tok
                self.salida += c_tok
                print(f"    [LLM local turn] {p_tok} in / {c_tok} out ({dur:.1f}s)", flush=True)
            self.llamadas += 1
            return r

        client.chat.completions.create = create


class LLMReferencia(BasePipelineElement):
    """Sustituto del LLM para --offline: pide de una vez las llamadas de referencia de la tarea
    (`ground_truth`) y luego responde con su `GROUND_TRUTH_OUTPUT`. No obedece inyecciones, así que
    solo sirve para comprobar que las defensas se ejecutan; no mide nada."""

    def __init__(self, suite, nombre: str) -> None:
        self.name = nombre
        self._por_prompt = {t.PROMPT: t for t in suite.user_tasks.values()}
        self._por_prompt.update({t.GOAL: t for t in suite.injection_tasks.values()})

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = {},
    ):
        tarea = self._por_prompt[query]
        if messages[-1]["role"] == "tool":
            msg = ChatAssistantMessage(
                role="assistant", content=[text_content_block_from_string(tarea.GROUND_TRUTH_OUTPUT)], tool_calls=None
            )
        else:
            msg = ChatAssistantMessage(
                role="assistant", content=[text_content_block_from_string("")], tool_calls=tarea.ground_truth(env)
            )
        return query, runtime, env, [*messages, msg], extra_args


def llm_openai(modelo: str, base_url: str | None = None) -> tuple[BasePipelineElement, ContadorTokens]:
    import openai
    from agentdojo.agent_pipeline import OpenAILLM

    is_local = "qwen" in modelo.lower() or "ollama" in modelo.lower() or "local" in modelo.lower() or (base_url is not None) or bool(os.getenv("OPENAI_BASE_URL"))
    url = base_url or os.getenv("OPENAI_BASE_URL") or ("http://localhost:11434/v1" if is_local else None)
    key = os.getenv("OPENAI_API_KEY") or ("ollama" if is_local else None)

    client = openai.OpenAI(base_url=url, api_key=key)
    contador = ContadorTokens(client)
    llm = OpenAILLM(client, modelo)
    llm.name = modelo.replace(":", "-").replace("/", "_")
    return llm, contador


# --- pipelines ------------------------------------------------------------------------


def construir(defensa: str, llm: BasePipelineElement, modelo: str):
    """Devuelve (pipeline, elemento_de_defensa_propio o None). El nombre del pipeline incluye el modelo
    (los ataques lo usan para dirigirse a él) y la defensa (separa las trazas en --logdir)."""
    modelo_seguro = modelo.replace(":", "-").replace("/", "_")
    sys_msg = load_system_message(None)
    if defensa in PROPIAS:
        det = {"keyword": KeywordDetector, "guard-detect": GuardDetect, "guard-sanitize": GuardSanitize}[defensa]()
        loop = ToolsExecutionLoop([ToolsExecutor(), det, llm])
        p = AgentPipeline([SystemMessage(sys_msg), InitQuery(), llm, loop])
    else:
        cfg = PipelineConfig(
            llm=llm, model_id=None, defense=None if defensa == "none" else defensa,
            system_message_name="default", system_message=sys_msg,
        )
        p, det = AgentPipeline.from_config(cfg), None

    conocido = any(nombre in modelo for nombre in MODEL_NAMES)
    p.name = f"{modelo_seguro}-{defensa}" if conocido else f"{modelo_seguro}-local-{defensa}"
    return p, det


# --- métricas -------------------------------------------------------------------------


def wilson(exitos: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = exitos / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - m, 4), round(c + m, 4)]


def tasa(valores) -> tuple[int, float | None, list[float] | None]:
    v = [bool(x) for x in valores]
    return len(v), (round(sum(v) / len(v), 4) if v else None), wilson(sum(v), len(v))


def percentil(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, math.ceil(q * len(xs)) - 1)], 2)


def _git() -> str | None:
    """git del PATH, o el de Git para Windows si no está en el PATH (variable GIT para otro)."""
    candidatos = [os.environ.get("GIT"), shutil.which("git"),
                  r"C:\Program Files\Git\cmd\git.exe", r"C:\Program Files\Git\ucrt64\bin\git.exe"]
    return next((c for c in candidatos if c and Path(c).exists()), None)


def commit_actual() -> str:
    git = _git()
    if git is None:
        return "sin-commit"
    try:
        h = subprocess.run([git, "rev-parse", "--short", "HEAD"], cwd=RAIZ, capture_output=True, text=True, check=True)
        sucio = subprocess.run([git, "status", "--porcelain"], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
        return h.stdout.strip() + ("-dirty" if sucio else "")
    except (OSError, subprocess.CalledProcessError):
        return "sin-commit"


def info_guardian() -> dict:
    """Modelo, decisión y umbral del guardián (o {"modelo": "mock"} con GUARD_MOCK=1)."""
    import guard

    return guard.describe()


# --- main -----------------------------------------------------------------------------


def correr_defensa(defensa: str, a, suite) -> dict:
    if a.offline:
        llm, contador = LLMReferencia(suite, a.modelo), None
    else:
        llm, contador = llm_openai(a.modelo, a.base_url)
    pipeline, det = construir(defensa, llm, a.modelo)
    ut, it = (a.user_task or None), (a.injection_task or None)
    n_ut = len(ut) if ut else len(suite.user_tasks)
    n_it = len(it) if it else len(suite.injection_tasks)

    print(f"\n==========================================================================")
    print(f"[*] DEFENSA: {defensa} (Pipeline: {pipeline.name} | Suite: {suite.name})")
    print(f"==========================================================================")

    with OutputLogger(str(a.logdir)):
        sin = None
        if not a.sin_utilidad:
            print(f" -> [Fase 1/2] Corriendo {n_ut} tarea(s) de usuario SIN ataque...", flush=True)
            t0_sin = time.perf_counter()
            sin = benchmark_suite_without_injections(
                pipeline, suite, logdir=a.logdir, force_rerun=a.force_rerun, user_tasks=ut, benchmark_version=a.version
            )
            print(f"    Fase 1 completada en {time.perf_counter() - t0_sin:.1f}s", flush=True)

        registro_sin = list(det.registro) if det else []
        if det:
            det.registro.clear()
        con = None
        if a.ataque != "ninguno":
            print(f" -> [Fase 2/2] Corriendo {n_ut * n_it} combinaciones CON ataque ({a.ataque})...", flush=True)
            t0_con = time.perf_counter()
            ataque = load_attack(a.ataque, suite, pipeline)
            con = benchmark_suite_with_injections(
                pipeline, suite, ataque, logdir=a.logdir, force_rerun=a.force_rerun,
                user_tasks=ut, injection_tasks=it, benchmark_version=a.version,
            )
            print(f"    Fase 2 completada en {time.perf_counter() - t0_con:.1f}s", flush=True)

        registro_con = list(det.registro) if det else []

    n_u, u, u_ic = tasa(sin["utility_results"].values()) if sin else (0, None, None)
    n_a, ua, ua_ic = tasa(con["utility_results"].values()) if con else (0, None, None)
    _, asr, asr_ic = tasa(con["security_results"].values()) if con else (0, None, None)
    registro = registro_sin + registro_con
    lat = [r["latencia_ms"] for r in registro if "latencia_ms" in r]
    fila = {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "commit": commit_actual(), "benchmark": "agentdojo",
        "suite": suite.name, "version": a.version, "modelo": "offline-referencia" if a.offline else a.modelo,
        "ataque": a.ataque, "defensa": defensa,
        "guard_modelo": info_guardian()["modelo"] if defensa.startswith("guard") else "",
        "n_utilidad": n_u, "utilidad": u, "utilidad_ic95": u_ic,
        "n_ataque": n_a, "utilidad_bajo_ataque": ua, "utilidad_bajo_ataque_ic95": ua_ic,
        "exito_ataque": asr, "exito_ataque_ic95": asr_ic,
        "salidas_revisadas": len(registro) if det else None,
        "salidas_marcadas": sum(not r["permitido"] for r in registro) if det else None,
        "latencia_guard_mediana_ms": round(statistics.median(lat), 2) if lat else None,
        "latencia_guard_p95_ms": percentil(lat, 0.95),
        "tokens_entrada": contador.entrada if contador else 0, "tokens_salida": contador.salida if contador else 0,
    }
    print(
        f"    [RESULTADO {defensa}] utilidad: {u} | utilidad bajo ataque: {ua} | éxito del ataque (ASR): {asr} | "
        f"revisadas: {fila['salidas_revisadas']} | marcadas: {fila['salidas_marcadas']}"
    )
    return {
        "resumen": fila,
        "config": {
            "argv": sys.argv, "pipeline": pipeline.name, "user_tasks": a.user_task, "injection_tasks": a.injection_task,
            "guardian": info_guardian() if defensa.startswith("guard") else None,
            "nota_tokens": "solo los de esta ejecución; los casos reutilizados de --logdir no suman",
        },
        "sin_ataque": {"utilidad": {k[0]: v for k, v in (sin or {}).get("utility_results", {}).items()}},
        "con_ataque": {
            "utilidad": {f"{k[0]}|{k[1]}": v for k, v in (con or {}).get("utility_results", {}).items()},
            "exito_ataque": {f"{k[0]}|{k[1]}": v for k, v in (con or {}).get("security_results", {}).items()},
        },
        "registro_guardian": {"sin_ataque": registro_sin, "con_ataque": registro_con},
    }


def guardar(res: dict, a) -> Path:
    fila = res["resumen"]
    destino = a.logdir if a.offline else RESULTADOS
    destino.mkdir(parents=True, exist_ok=True)
    nombre = f"{datetime.now():%Y-%m-%d}-{fila['commit']}-agentdojo-{fila['suite']}-{fila['defensa']}"
    if a.offline:
        nombre += "-offline"
    ruta = destino / f"{nombre}.json"
    fila["archivo"] = str(ruta.relative_to(RAIZ)) if ruta.is_relative_to(RAIZ) else str(ruta)
    ruta.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    if not a.offline:
        resumen = RESULTADOS / "summary.csv"
        nuevo = not resumen.exists()
        with resumen.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNAS)
            if nuevo:
                w.writeheader()
            w.writerow({k: json.dumps(v) if isinstance(v, list) else v for k, v in fila.items()})
    return ruta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-s", "--suite", default="banking", choices=["banking", "workspace", "slack", "travel"])
    ap.add_argument("-d", "--defensa", action="append",
                    help=f"repetible o separado por comas (ej: -d none,guard-sanitize); por defecto: {' '.join(TODAS)}")
    ap.add_argument("-ut", "--user-task", action="append", default=[], help="repetible; por defecto todas")
    ap.add_argument("-it", "--injection-task", action="append", default=[], help="repetible; por defecto todas")
    ap.add_argument("--modelo", default="qwen3:8b", help="Modelo de LLM (por defecto qwen3:8b en Ollama local)")
    ap.add_argument("--base-url", default=None, help="URL base de API OpenAI-compatible (por defecto http://localhost:11434/v1 para local)")
    ap.add_argument("--ataque", default="important_instructions", help="'ninguno' para medir solo utilidad")
    ap.add_argument("--version", default="v1.2.2", help="versión del benchmark de AgentDojo")
    ap.add_argument("--logdir", type=Path, default=RAIZ / "runs")
    ap.add_argument("--force-rerun", action="store_true", help="forzar reevaluación completa sin usar caché de corridas previas")
    ap.add_argument("--sin-utilidad", action="store_true", help="omitir la corrida sin ataque (ahorra tiempo)")
    ap.add_argument("--offline", action="store_true", help="sin API: el LLM ejecuta las llamadas de referencia")
    args = ap.parse_args()

    # Procesar defensas permitiendo tanto `-d none,guard-sanitize` como `-d none -d guard-sanitize`
    raw_defensas = args.defensa or list(TODAS)
    defensas: list[str] = []
    valid_defenses = {*TODAS, *DEFENSES}
    for d in raw_defensas:
        for sub_d in d.split(","):
            sub_d = sub_d.strip()
            if sub_d:
                if sub_d not in valid_defenses:
                    sys.exit(f"Defensa desconocida: '{sub_d}'. Opciones válidas: {sorted(valid_defenses)}")
                if sub_d not in defensas:
                    defensas.append(sub_d)

    is_local = "qwen" in args.modelo.lower() or "ollama" in args.modelo.lower() or args.base_url or os.getenv("OPENAI_BASE_URL")
    if not args.offline and not is_local:
        from dotenv import load_dotenv

        load_dotenv(RAIZ / ".env")
        if not os.environ.get("OPENAI_API_KEY"):
            sys.exit("Falta OPENAI_API_KEY (variable de entorno o .env). Para usar Ollama local: --modelo qwen3:8b")
    elif args.offline:
        args.logdir = args.logdir / "offline"

    # Calentamiento inicial único (evita que los ~15s de carga de embeddings sesguen las latencias)
    if any(d.startswith("guard") for d in defensas):
        print("\n[+] Calentando modelo del guardián y cargando pesos en CPU...", flush=True)
        t0_cal = time.perf_counter()
        try:
            import guard
            guard.warmup()
        except Exception:
            os.environ["GUARD_MOCK"] = "1"
        print(f"[+] Calentamiento finalizado en {time.perf_counter() - t0_cal:.1f}s.\n", flush=True)

    suite = get_suite(args.version, args.suite)
    for d in defensas:
        res = correr_defensa(d, args, suite)
        print(f"    -> Archivo guardado: {guardar(res, args)}\n")


if __name__ == "__main__":
    main()
