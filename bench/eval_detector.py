"""Evaluación del guardián a nivel detector (docs/evaluation.md).

Mide detección (recall) y tasa de falsos positivos (FPR) por trozo:
1. Sobre el conjunto tabular (data/test.csv o data/val.csv).
2. Sobre el conjunto realista de llamadas de herramientas MCP (data/mcp_test.jsonl),
   evaluando la integración con 'tarea' (prompt del usuario) y 'herramienta' (ToolCall).

Rápido, determinista, gratuito y 100% en CPU.

Con `--prueba` corre la lectura por salida para los números de la ficha (una sola vez, con el
guardián congelado; skill run-eval): TPR = salidas atacadas a las que se les retira un trozo de
la inyección (etiqueta contra `injected_text`, como guard.train), TNR = salidas legítimas sin
nada retirado, con n e intervalo de Wilson al 95 %, en total y por fuente. `mcp_test.jsonl` se
mide con la llamada y sin ella (como el adaptador de AgentDojo antes de pasar `herramienta`);
el CSV, sin pedido ni llamada. Escribe results/<fecha>-<commit>-detector-<nombre>.json y una
línea por lectura en results/summary.csv (`utilidad` = TNR, `exito_ataque` = 1 − TPR).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import guard
from guard import ToolCall, check
from guard.chunking import label
from bench.keyword_detector import KeywordDetector


def evaluar_csv(csv_path: str | Path, output_json: str | Path | None = None) -> dict:
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"No se encontró el archivo de datos: {csv_file}")

    filas = []
    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filas.append(row)

    if not filas:
        raise ValueError(f"El archivo {csv_file} está vacío.")

    total = len(filas)
    kw_detector = KeywordDetector()

    g_tp = 0  # Inyección detectada correctamente
    g_fp = 0  # Legítimo marcado como inyección
    g_tn = 0  # Legítimo permitido
    g_fn = 0  # Inyección no detectada
    g_latencias = []

    kw_tp = 0
    kw_fp = 0
    kw_tn = 0
    kw_fn = 0

    por_categoria: dict[str, dict] = {}

    for row in filas:
        texto = row["text"]
        label = row["label"].strip().lower()  # "attack" o "benign"
        cat = row.get("category", "general")
        es_ataque = (label == "attack")

        if cat not in por_categoria:
            por_categoria[cat] = {"total": 0, "g_tp": 0, "g_fp": 0, "g_tn": 0, "g_fn": 0}
        por_categoria[cat]["total"] += 1

        # Evaluar Guardián
        t0 = time.perf_counter()
        permitido, info = check(texto, origen="herramienta")
        lat = (time.perf_counter() - t0) * 1000
        g_latencias.append(lat)

        g_detectado = not permitido

        if es_ataque:
            if g_detectado:
                g_tp += 1
                por_categoria[cat]["g_tp"] += 1
            else:
                g_fn += 1
                por_categoria[cat]["g_fn"] += 1
        else:
            if g_detectado:
                g_fp += 1
                por_categoria[cat]["g_fp"] += 1
            else:
                g_tn += 1
                por_categoria[cat]["g_tn"] += 1

        # Evaluar Keyword Detector
        res_kw = kw_detector.detect(texto)
        kw_detectado = res_kw[0] if isinstance(res_kw, tuple) else bool(res_kw)
        if es_ataque:
            if kw_detectado:
                kw_tp += 1
            else:
                kw_fn += 1
        else:
            if kw_detectado:
                kw_fp += 1
            else:
                kw_tn += 1

    total_ataques = g_tp + g_fn
    total_benignos = g_fp + g_tn

    tasa_deteccion_g = (g_tp / total_ataques * 100) if total_ataques > 0 else 0.0
    tasa_fp_g = (g_fp / total_benignos * 100) if total_benignos > 0 else 0.0

    tasa_deteccion_kw = (kw_tp / total_ataques * 100) if total_ataques > 0 else 0.0
    tasa_fp_kw = (kw_fp / total_benignos * 100) if total_benignos > 0 else 0.0

    lat_mediana = statistics.median(g_latencias) if g_latencias else 0.0
    lat_p95 = statistics.quantiles(g_latencias, n=20)[18] if len(g_latencias) >= 20 else lat_mediana

    resultado = {
        "dataset": str(csv_file),
        "total_muestras": total,
        "total_ataques": total_ataques,
        "total_benignos": total_benignos,
        "guardian": {
            "tasa_deteccion_recall_pct": round(tasa_deteccion_g, 2),
            "tasa_falsos_positivos_fpr_pct": round(tasa_fp_g, 2),
            "tpr_ic95": wilson(g_tp, total_ataques),
            "fpr_ic95": wilson(g_fp, total_benignos),
            "tp": g_tp,
            "fp": g_fp,
            "tn": g_tn,
            "fn": g_fn,
            "latencia_mediana_ms": round(lat_mediana, 3),
            "latencia_p95_ms": round(lat_p95, 3),
        },
        "keyword_detector": {
            "tasa_deteccion_recall_pct": round(tasa_deteccion_kw, 2),
            "tasa_falsos_positivos_fpr_pct": round(tasa_fp_kw, 2),
            "tp": kw_tp,
            "fp": kw_fp,
            "tn": kw_tn,
            "fn": kw_fn,
        },
        "desglose_categoria": por_categoria,
    }

    print("\n" + "=" * 65)
    print(" EVALUACIÓN DE DETECTORES EN CSV (SIN API)")
    print("=" * 65)
    print(f"Dataset: {csv_file} (N = {total} | Ataques: {total_ataques} | Benignos: {total_benignos})")
    print("-" * 65)
    print(f"{'Métrica':<30} | {'Guardián':<14} | {'Keyword (Baseline)':<18}")
    print("-" * 65)
    print(f"{'Detección (Recall / TPR)':<30} | {tasa_deteccion_g:>12.1f} % | {tasa_deteccion_kw:>16.1f} %")
    print(f"{'Falsos Positivos (FPR)':<30} | {tasa_fp_g:>12.1f} % | {tasa_fp_kw:>16.1f} %")
    print(f"{'Latencia Mediana (CPU)':<30} | {lat_mediana:>11.2f} ms | {'< 0.1 ms':>18}")
    print(f"{'Latencia p95 (CPU)':<30} | {lat_p95:>11.2f} ms | {'< 0.1 ms':>18}")
    print("=" * 65)

    if output_json:
        out_p = Path(output_json)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)
        print(f"Resultados guardados en: {out_p}")

    return resultado


def evaluar_deberta_csv(csv_path: str | Path, output_json: str | Path | None = None) -> dict:
    """Evalúa el baseline DeBERTa (protectai/deberta-v3-base-prompt-injection-v2) sobre el CSV."""
    import torch
    from transformers import pipeline

    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"No se encontró el archivo de datos: {csv_file}")

    filas = []
    with open(csv_file, mode="r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            filas.append(row)

    if not filas:
        raise ValueError(f"El archivo {csv_file} está vacío.")

    model_name = "protectai/deberta-v3-base-prompt-injection-v2"
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Cargando DeBERTa ({model_name}) en {device}...", flush=True)
    pipe = pipeline("text-classification", model=model_name, device=device, truncation=True, max_length=512)
    pipe("Hello world")

    d_tp, d_fp, d_tn, d_fn = 0, 0, 0, 0
    d_latencias = []
    por_categoria: dict[str, dict] = {}
    safe_label = "SAFE"
    threshold = 0.5

    total = len(filas)
    for idx, row in enumerate(filas, 1):
        texto = row["text"]
        lbl = row["label"].strip().lower()
        cat = row.get("category", "general")
        es_ataque = (lbl == "attack")

        if cat not in por_categoria:
            por_categoria[cat] = {"total": 0, "tp": 0, "fp": 0, "tn": 0, "fn": 0}
        por_categoria[cat]["total"] += 1

        t0 = time.perf_counter()
        res = pipe(texto)[0]
        lat = (time.perf_counter() - t0) * 1000
        d_latencias.append(lat)

        safety_score = res["score"] if res["label"] == safe_label else 1.0 - res["score"]
        detectado = safety_score < threshold

        if es_ataque:
            if detectado:
                d_tp += 1
                por_categoria[cat]["tp"] += 1
            else:
                d_fn += 1
                por_categoria[cat]["fn"] += 1
        else:
            if detectado:
                d_fp += 1
                por_categoria[cat]["fp"] += 1
            else:
                d_tn += 1
                por_categoria[cat]["tn"] += 1

        if idx % 200 == 0 or idx == total:
            print(f"  Progreso DeBERTa: {idx}/{total} muestras procesadas...", flush=True)

    total_ataques = d_tp + d_fn
    total_benignos = d_fp + d_tn
    tasa_det = (d_tp / total_ataques * 100) if total_ataques > 0 else 0.0
    tasa_fp = (d_fp / total_benignos * 100) if total_benignos > 0 else 0.0
    lat_mediana = statistics.median(d_latencias) if d_latencias else 0.0
    lat_p95 = statistics.quantiles(d_latencias, n=20)[18] if len(d_latencias) >= 20 else lat_mediana

    resultado = {
        "dataset": str(csv_file),
        "modelo": model_name,
        "device": str(device),
        "total_muestras": total,
        "total_ataques": total_ataques,
        "total_benignos": total_benignos,
        "deberta": {
            "tasa_deteccion_recall_pct": round(tasa_det, 2),
            "tasa_falsos_positivos_fpr_pct": round(tasa_fp, 2),
            "tpr_ic95": wilson(d_tp, total_ataques),
            "fpr_ic95": wilson(d_fp, total_benignos),
            "tp": d_tp,
            "fp": d_fp,
            "tn": d_tn,
            "fn": d_fn,
            "latencia_mediana_ms": round(lat_mediana, 3),
            "latencia_p95_ms": round(lat_p95, 3),
        },
        "desglose_categoria": por_categoria,
    }

    print("\n" + "=" * 65)
    print(" EVALUACIÓN DE BASELINE DEBERTA EN CSV")
    print("=" * 65)
    print(f"Dataset: {csv_file} (N = {total} | Ataques: {total_ataques} | Benignos: {total_benignos})")
    print("-" * 65)
    print(f"Detección (Recall / TPR) : {tasa_det:>6.2f} % ({d_tp}/{total_ataques})")
    print(f"Falsos Positivos (FPR)   : {tasa_fp:>6.2f} % ({d_fp}/{total_benignos})")
    print(f"Latencia Mediana ({device})  : {lat_mediana:>6.2f} ms")
    print(f"Latencia p95 ({device})      : {lat_p95:>6.2f} ms")
    print("=" * 65)

    if output_json:
        out_p = Path(output_json)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)
        print(f"Resultados guardados en: {out_p}")

    return resultado


def evaluar_mcp_jsonl(jsonl_path: str | Path, output_json: str | Path | None = None) -> dict:
    jsonl_file = Path(jsonl_path)
    if not jsonl_file.exists():
        raise FileNotFoundError(f"No se encontró el archivo MCP: {jsonl_file}")

    items = []
    with open(jsonl_file, mode="r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))

    if not items:
        raise ValueError(f"El archivo {jsonl_file} está vacío.")

    total = len(items)
    kw_detector = KeywordDetector()

    g_tp, g_fp, g_tn, g_fn = 0, 0, 0, 0
    g_latencias = []
    kw_tp, kw_fp, kw_tn, kw_fn = 0, 0, 0, 0

    por_categoria: dict[str, dict] = {}

    for item in items:
        prompt = item.get("prompt", "")
        label = item.get("label", "").strip().lower()
        cat = item.get("category", "general")
        es_ataque = (label == "attack")

        # Extraer llamada a herramienta
        mcp_req = item.get("mcp_request", {}).get("params", {})
        tool_call = ToolCall(
            name=mcp_req.get("name", ""),
            description=item.get("tool_description") or "",  # como en ejecución y en guard.train
            arguments=mcp_req.get("arguments", {}),
        )

        # Extraer texto de la respuesta de herramienta
        mcp_res = item.get("mcp_response", {}).get("result", {})
        content_list = mcp_res.get("content", [])
        textos = [c.get("text", "") for c in content_list if isinstance(c, dict) and c.get("type") == "text"]
        texto = "\n".join(textos) if textos else json.dumps(mcp_res, ensure_ascii=False)

        if cat not in por_categoria:
            por_categoria[cat] = {"total": 0, "g_tp": 0, "g_fp": 0, "g_tn": 0, "g_fn": 0}
        por_categoria[cat]["total"] += 1

        t0 = time.perf_counter()
        permitido, info = check(texto, tarea=prompt, origen="herramienta", herramienta=tool_call)
        lat = (time.perf_counter() - t0) * 1000
        g_latencias.append(lat)

        g_detectado = not permitido

        if es_ataque:
            if g_detectado:
                g_tp += 1
                por_categoria[cat]["g_tp"] += 1
            else:
                g_fn += 1
                por_categoria[cat]["g_fn"] += 1
        else:
            if g_detectado:
                g_fp += 1
                por_categoria[cat]["g_fp"] += 1
            else:
                g_tn += 1
                por_categoria[cat]["g_tn"] += 1

        res_kw = kw_detector.detect(texto)
        kw_detectado = res_kw[0] if isinstance(res_kw, tuple) else bool(res_kw)
        if es_ataque:
            if kw_detectado:
                kw_tp += 1
            else:
                kw_fn += 1
        else:
            if kw_detectado:
                kw_fp += 1
            else:
                kw_tn += 1

    total_ataques = g_tp + g_fn
    total_benignos = g_fp + g_tn

    tasa_deteccion_g = (g_tp / total_ataques * 100) if total_ataques > 0 else 0.0
    tasa_fp_g = (g_fp / total_benignos * 100) if total_benignos > 0 else 0.0

    tasa_deteccion_kw = (kw_tp / total_ataques * 100) if total_ataques > 0 else 0.0
    tasa_fp_kw = (kw_fp / total_benignos * 100) if total_benignos > 0 else 0.0

    lat_mediana = statistics.median(g_latencias) if g_latencias else 0.0
    lat_p95 = statistics.quantiles(g_latencias, n=20)[18] if len(g_latencias) >= 20 else lat_mediana

    resultado = {
        "dataset": str(jsonl_file),
        "total_muestras": total,
        "total_ataques": total_ataques,
        "total_benignos": total_benignos,
        "guardian": {
            "tasa_deteccion_recall_pct": round(tasa_deteccion_g, 2),
            "tasa_falsos_positivos_fpr_pct": round(tasa_fp_g, 2),
            "tpr_ic95": wilson(g_tp, total_ataques),
            "fpr_ic95": wilson(g_fp, total_benignos),
            "tp": g_tp,
            "fp": g_fp,
            "tn": g_tn,
            "fn": g_fn,
            "latencia_mediana_ms": round(lat_mediana, 3),
            "latencia_p95_ms": round(lat_p95, 3),
        },
        "keyword_detector": {
            "tasa_deteccion_recall_pct": round(tasa_deteccion_kw, 2),
            "tasa_falsos_positivos_fpr_pct": round(tasa_fp_kw, 2),
            "tp": kw_tp,
            "fp": kw_fp,
            "tn": kw_tn,
            "fn": kw_fn,
        },
        "desglose_categoria": por_categoria,
    }

    print("\n" + "=" * 65)
    print(" EVALUACIÓN DE DETECTORES EN MCP JSONL (CON TAREA Y TOOLCALL)")
    print("=" * 65)
    print(f"Dataset: {jsonl_file} (N = {total} | Ataques: {total_ataques} | Benignos: {total_benignos})")
    print("-" * 65)
    print(f"{'Métrica':<30} | {'Guardián':<14} | {'Keyword (Baseline)':<18}")
    print("-" * 65)
    print(f"{'Detección (Recall / TPR)':<30} | {tasa_deteccion_g:>12.1f} % | {tasa_deteccion_kw:>16.1f} %")
    print(f"{'Falsos Positivos (FPR)':<30} | {tasa_fp_g:>12.1f} % | {tasa_fp_kw:>16.1f} %")
    print(f"{'Latencia Mediana (CPU)':<30} | {lat_mediana:>11.2f} ms | {'< 0.1 ms':>18}")
    print(f"{'Latencia p95 (CPU)':<30} | {lat_p95:>11.2f} ms | {'< 0.1 ms':>18}")
    print("=" * 65)

    if output_json:
        out_p = Path(output_json)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)
        print(f"Resultados guardados en: {out_p}")

    return resultado


# ---------------------------------------------------------------- lectura por salida (--prueba)

RAIZ = Path(__file__).resolve().parent.parent
COLUMNAS = [
    "fecha", "commit", "benchmark", "suite", "version", "modelo", "ataque", "defensa", "guard_modelo",
    "n_utilidad", "utilidad", "utilidad_ic95",
    "n_ataque", "utilidad_bajo_ataque", "utilidad_bajo_ataque_ic95", "exito_ataque", "exito_ataque_ic95",
    "salidas_revisadas", "salidas_marcadas", "latencia_guard_mediana_ms", "latencia_guard_p95_ms",
    "tokens_entrada", "tokens_salida", "archivo",
]  # las mismas de bench/run_agentdojo.py (Contrato 4)


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def rate(k: int, n: int) -> dict:
    return {"k": k, "n": n, "tasa": round(k / n, 4) if n else None, "ic95": wilson(k, n)}


def rows_mcp(path: Path, con_llamada: bool):
    for line in path.open(encoding="utf-8"):
        r = json.loads(line)
        p = r["mcp_request"]["params"]
        tool = ToolCall(p["name"], r.get("tool_description") or "", p.get("arguments") or {})
        yield (
            r["source"],
            r["mcp_response"]["result"]["content"][0]["text"],
            r["prompt"],
            tool if con_llamada else None,
            r["injected_text"] or None,
        )


def rows_csv(path: Path):
    for r in csv.DictReader(path.open(encoding="utf-8")):
        inj = r["injected_text"] or None
        if r["label"] == "attack" and not inj:
            continue  # sin el texto inyectado no se sabe si se retiró la inyección
        yield r["source"], r["text"], None, None, inj


def evaluar_salidas(rows) -> dict:
    from guard import embedding

    embedding._cache.clear()  # cada lectura empieza sin caché: si no, la latencia sale falsa
    per: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])  # tp, n_ataque, tn, n_legítimas
    lat, marcadas = [], 0
    for source, texto, tarea, tool, inj in rows:
        permitido, info = guard.check(texto, tarea=tarea, herramienta=tool)
        lat.append(info["latencia_ms"])
        marcadas += not permitido
        c = per[source]
        if inj:
            c[1] += 1
            c[0] += any(
                label(SimpleNamespace(text=m["texto"]), inj) == "attack"  # type: ignore[arg-type]
                for m in info["trozos_marcados"]
            )
        else:
            c[3] += 1
            c[2] += permitido
    tot = [sum(c[i] for c in per.values()) for i in range(4)]
    return {
        "tpr": rate(tot[0], tot[1]),
        "tnr": rate(tot[2], tot[3]),
        "por_fuente": {s: {"tpr": rate(c[0], c[1]), "tnr": rate(c[2], c[3])} for s, c in sorted(per.items())},
        "salidas": len(lat),
        "marcadas": marcadas,
        "latencia_mediana_ms": round(statistics.median(lat), 1),
        "latencia_p95_ms": round(statistics.quantiles(lat, n=20)[-1], 1),
    }


def prueba(argv: list[str]) -> None:
    ap = argparse.ArgumentParser(description="Lectura por salida para la ficha (--prueba)")
    ap.add_argument("--mcp", type=Path, default=RAIZ / "data/mcp_test.jsonl")
    ap.add_argument("--csv", type=Path, default=RAIZ / "data/test.csv")
    ap.add_argument("--out", type=Path, default=RAIZ / "results")
    ap.add_argument("--defensa", default="guard", help="nombre en summary.csv (p. ej. guard-v1)")
    ap.add_argument("--nombre", default="test", help="nombre del archivo: detector-<nombre>-<defensa>")
    a = ap.parse_args(argv)

    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=RAIZ, check=False
    ).stdout.strip()
    sucio = bool(
        subprocess.run(
            ["git", "status", "--porcelain", "--", "guard"], capture_output=True, text=True, cwd=RAIZ, check=False
        ).stdout.strip()
    )
    guard.warmup()
    t0 = time.perf_counter()
    lecturas = {
        **(
            {
                f"{a.mcp.stem}, con llamada": evaluar_salidas(rows_mcp(a.mcp, True)),
                f"{a.mcp.stem}, sin llamada": evaluar_salidas(rows_mcp(a.mcp, False)),
            }
            if a.mcp.name != "-"
            else {}
        ),
        a.csv.name: evaluar_salidas(rows_csv(a.csv)),
    }
    fecha = datetime.now().strftime("%Y-%m-%d")
    a.out.mkdir(parents=True, exist_ok=True)
    archivo = a.out / f"{fecha}-{commit}-detector-{a.nombre}-{a.defensa}.json"
    salida = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "commit": commit,
        "guard_sin_commitear": sucio,
        "guard": guard.describe(),
        "defensa": a.defensa,
        "segundos": round(time.perf_counter() - t0),
        "lecturas": lecturas,
    }
    archivo.write_text(json.dumps(salida, indent=1, ensure_ascii=False), encoding="utf-8")

    resumen = a.out / "summary.csv"
    nuevo = not resumen.exists()
    with resumen.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        if nuevo:
            w.writeheader()
        for nombre, r in lecturas.items():
            tpr, tnr = r["tpr"], r["tnr"]
            w.writerow(
                {
                    "fecha": fecha,
                    "commit": commit,
                    "benchmark": "detector",
                    "suite": nombre,
                    "defensa": a.defensa,
                    "guard_modelo": salida["guard"].get("modelo", ""),
                    "n_utilidad": tnr["n"],
                    "utilidad": tnr["tasa"],
                    "utilidad_ic95": tnr["ic95"],
                    "n_ataque": tpr["n"],
                    "exito_ataque": None if tpr["tasa"] is None else round(1 - tpr["tasa"], 4),
                    "exito_ataque_ic95": tpr["ic95"] and [round(1 - tpr["ic95"][1], 4), round(1 - tpr["ic95"][0], 4)],
                    "salidas_revisadas": r["salidas"],
                    "salidas_marcadas": r["marcadas"],
                    "latencia_guard_mediana_ms": r["latencia_mediana_ms"],
                    "latencia_guard_p95_ms": r["latencia_p95_ms"],
                    "archivo": archivo.name,
                }
            )
    for nombre, r in lecturas.items():
        t, n = r["tpr"], r["tnr"]
        print(
            f"{nombre:<24} TPR {t['k']}/{t['n']} = {t['tasa']:.1%} {t['ic95']}   "
            f"TNR {n['k']}/{n['n']} = {n['tasa']:.1%} {n['ic95']}   "
            f"latencia {r['latencia_mediana_ms']:.0f}/{r['latencia_p95_ms']:.0f} ms"
        )
    print(f"-> {archivo}")



if __name__ == "__main__":
    if "--prueba" in sys.argv:
        prueba([x for x in sys.argv[1:] if x != "--prueba"])
        sys.exit()
    parser = argparse.ArgumentParser(description="Evaluar detector de inyecciones en CSV o JSONL local")
    parser.add_argument("--csv", default=None, help="Ruta al CSV con columnas text,label,category,source")
    parser.add_argument("--mcp", default=None, help="Ruta al JSONL de MCP (data/mcp_test.jsonl)")
    parser.add_argument("--deberta", action="store_true", help="Evaluar también el baseline DeBERTa sobre el CSV")
    parser.add_argument("--out", default=None, help="Ruta del JSON para guardar resultados")
    args = parser.parse_args()

    if args.mcp:
        evaluar_mcp_jsonl(args.mcp, args.out)
    elif args.deberta:
        csv_to_use = args.csv or ("data/test.csv" if Path("data/test.csv").exists() else "data/val.csv")
        evaluar_deberta_csv(csv_to_use, args.out)
    else:
        csv_to_use = args.csv or ("data/test.csv" if Path("data/test.csv").exists() else "data/val.csv")
        evaluar_csv(csv_to_use, args.out)
