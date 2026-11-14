"""Evaluación del guardián a nivel detector (docs/evaluation.md).

Mide detección (recall) y tasa de falsos positivos (FPR) por trozo:
1. Sobre el conjunto tabular (data/test.csv o data/val.csv).
2. Sobre el conjunto realista de llamadas de herramientas MCP (data/mcp_test.jsonl),
   evaluando la integración con 'tarea' (prompt del usuario) y 'herramienta' (ToolCall).

Rápido, determinista, gratuito y 100% en CPU.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from guard import ToolCall, check
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluar detector de inyecciones en CSV o JSONL local")
    parser.add_argument("--csv", default=None, help="Ruta al CSV con columnas text,label,category,source")
    parser.add_argument("--mcp", default=None, help="Ruta al JSONL de MCP (data/mcp_test.jsonl)")
    parser.add_argument("--out", default=None, help="Ruta del JSON para guardar resultados")
    args = parser.parse_args()

    if args.mcp:
        evaluar_mcp_jsonl(args.mcp, args.out)
    else:
        csv_to_use = args.csv or ("data/test.csv" if Path("data/test.csv").exists() else "data/val.csv")
        evaluar_csv(csv_to_use, args.out)
