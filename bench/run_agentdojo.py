"""Corre AgentDojo con varias defensas (mismo modelo, misma suite, mismas tareas) y escribe results/.

Ejemplos:

    # piloto barato: 2 tareas x 2 inyecciones, todas las defensas
    python -m bench.run_agentdojo -s banking -ut user_task_0 -ut user_task_1 \
        -it injection_task_0 -it injection_task_1

    # prueba de integración SIN API: el "LLM" ejecuta las llamadas de referencia de cada tarea
    python -m bench.run_agentdojo --offline -s banking -ut user_task_0 -it injection_task_0

Defensas: none, keyword, transformers_pi_detector (DeBERTa), guard-detect, guard-sanitize,
y las demás de AgentDojo (tool_filter, spotlighting_with_delimiting, repeat_user_prompt).

Cada defensa escribe results/<fecha>-<commit>-agentdojo-<suite>-<defensa>.json y una línea en
results/summary.csv (Contrato 4). Las trazas completas de AgentDojo quedan en --logdir (runs/);
si se repite un comando, AgentDojo reutiliza los casos ya corridos (no se paga dos veces).
Con --offline solo se escribe en --logdir: esos números no son resultados.

La clave va en OPENAI_API_KEY (o en .env), nunca en el repo.
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
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

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
from agentdojo.benchmark import benchmark_suite_with_injections, benchmark_suite_without_injections
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionsRuntime
from agentdojo.logging import OutputLogger
from agentdojo.task_suite.load_suites import get_suite
from agentdojo.types import ChatAssistantMessage, ChatMessage, text_content_block_from_string

from bench.agentdojo_guard import GuardDetect, GuardSanitize
from bench.keyword_detector import KeywordDetector

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
            r = original(*args, **kwargs)
            if getattr(r, "usage", None) is not None:
                self.entrada += r.usage.prompt_tokens or 0
                self.salida += r.usage.completion_tokens or 0
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


def llm_openai(modelo: str) -> tuple[BasePipelineElement, ContadorTokens]:
    import openai
    from agentdojo.agent_pipeline import OpenAILLM

    client = openai.OpenAI()
    contador = ContadorTokens(client)
    llm = OpenAILLM(client, modelo)
    llm.name = modelo
    return llm, contador


# --- pipelines ------------------------------------------------------------------------


def construir(defensa: str, llm: BasePipelineElement, modelo: str):
    """Devuelve (pipeline, elemento_de_defensa_propio o None). El nombre del pipeline incluye el modelo
    (los ataques lo usan para dirigirse a él) y la defensa (separa las trazas en --logdir)."""
    if defensa in PROPIAS:
        det = {"keyword": KeywordDetector, "guard-detect": GuardDetect, "guard-sanitize": GuardSanitize}[defensa]()
        loop = ToolsExecutionLoop([ToolsExecutor(), det, llm])
        p = AgentPipeline([SystemMessage(load_system_message(None)), InitQuery(), llm, loop])
    else:
        cfg = PipelineConfig(
            llm=llm, model_id=None, defense=None if defensa == "none" else defensa,
            system_message_name=None, system_message=None,
        )
        p, det = AgentPipeline.from_config(cfg), None
    p.name = f"{modelo}-{defensa}"
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
    if os.environ.get("GUARD_MOCK") == "1":
        return {"modelo": "mock"}
    from guard import config
    from guard.model import cargar

    p = cargar()
    return {"modelo": config.MODELO, "tau_alto": p.tau_alto, "tau_bajo": p.tau_bajo, "tau_drift": p.tau_drift, "notas": p.notas}


# --- main -----------------------------------------------------------------------------


def correr_defensa(defensa: str, a, suite) -> dict:
    if a.offline:
        llm, contador = LLMReferencia(suite, a.modelo), None
    else:
        llm, contador = llm_openai(a.modelo)
    pipeline, det = construir(defensa, llm, a.modelo)
    ut, it = (a.user_task or None), (a.injection_task or None)
    print(f"\n=== {defensa}  ({pipeline.name}, suite {suite.name})")

    with OutputLogger(str(a.logdir)):
        sin = None
        if not a.sin_utilidad:
            sin = benchmark_suite_without_injections(
                pipeline, suite, logdir=a.logdir, force_rerun=a.force_rerun, user_tasks=ut, benchmark_version=a.version
            )
        registro_sin = list(det.registro) if det else []
        if det:
            det.registro.clear()
        con = None
        if a.ataque != "ninguno":
            ataque = load_attack(a.ataque, suite, pipeline)
            con = benchmark_suite_with_injections(
                pipeline, suite, ataque, logdir=a.logdir, force_rerun=a.force_rerun,
                user_tasks=ut, injection_tasks=it, benchmark_version=a.version,
            )
        registro_con = list(det.registro) if det else []

    n_u, u, u_ic = tasa(sin["utility_results"].values()) if sin else (0, None, None)
    n_a, ua, ua_ic = tasa(con["utility_results"].values()) if con else (0, None, None)
    _, asr, asr_ic = tasa(con["security_results"].values()) if con else (0, None, None)  # True = el ataque ganó
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
        f"    utilidad {u}  utilidad bajo ataque {ua}  éxito del ataque {asr}  "
        f"(n={n_u}/{n_a}; marcadas {fila['salidas_marcadas']}/{fila['salidas_revisadas']}; "
        f"tokens {fila['tokens_entrada']}+{fila['tokens_salida']})"
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
    ap.add_argument("-d", "--defensa", action="append", choices=sorted({*TODAS, *DEFENSES}),
                    help=f"repetible; por defecto: {' '.join(TODAS)}")
    ap.add_argument("-ut", "--user-task", action="append", default=[], help="repetible; por defecto todas")
    ap.add_argument("-it", "--injection-task", action="append", default=[], help="repetible; por defecto todas")
    ap.add_argument("--modelo", default="gpt-4o-mini-2024-07-18")
    ap.add_argument("--ataque", default="important_instructions", help="'ninguno' para medir solo utilidad")
    ap.add_argument("--version", default="v1.2.2", help="versión del benchmark de AgentDojo")
    ap.add_argument("--logdir", type=Path, default=RAIZ / "runs")
    ap.add_argument("--force-rerun", action="store_true", help="no reutilizar casos ya corridos en --logdir")
    ap.add_argument("--sin-utilidad", action="store_true", help="omitir la corrida sin ataque (ahorra tokens)")
    ap.add_argument("--offline", action="store_true", help="sin API: el LLM ejecuta las llamadas de referencia")
    a = ap.parse_args()

    if not a.offline:
        from dotenv import load_dotenv

        load_dotenv(RAIZ / ".env")
        if not os.environ.get("OPENAI_API_KEY"):
            sys.exit("Falta OPENAI_API_KEY (variable de entorno o .env). Para probar sin API: --offline")
    else:
        a.logdir = a.logdir / "offline"

    defensas = a.defensa or list(TODAS)
    if any(d.startswith("guard") for d in defensas):
        from guard import check

        check("Calentamiento: carga el modelo de embeddings antes de medir latencias.")
    suite = get_suite(a.version, a.suite)
    for d in defensas:
        print(f"    -> {guardar(correr_defensa(d, a, suite), a)}")


if __name__ == "__main__":
    main()
