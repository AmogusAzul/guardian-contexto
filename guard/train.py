"""Ajusta el guardián y elige los umbrales (docs/algorithm.md, docs/evaluation.md).

    python -m guard.train                      # data/train.csv + data/val.csv (o data/seed.csv si no existen)
    GUARD_MODEL=potion python -m guard.train   # otro modelo de embeddings

Escribe guard/artifacts/<modelo>.json. Nunca usar textos de AgentDojo aquí.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from guard import config
from guard.chunks import oraciones, trozos
from guard.embed import embed
from guard.model import Parametros, ajustar


def leer(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8", newline="") as f:
        filas = [r for r in csv.DictReader(f) if r["text"].strip()]
    malas = {r["label"] for r in filas} - {"attack", "benign"}
    if malas:
        sys.exit(f"{ruta}: etiquetas desconocidas {malas}")
    return filas


def max_coseno(p: Parametros, textos: list[str]) -> np.ndarray:
    """Por texto, el mayor coseno crudo con la dirección de ataque entre sus trozos (como en check())."""
    todos, dueño = [], []
    for i, texto in enumerate(textos):
        for t in trozos(texto, oraciones(texto)) or [None]:
            todos.append(t.texto if t else texto)
            dueño.append(i)
    crudo = p.coseno_ataque(p.centrar(embed(todos, p.modelo)))
    out = np.full(len(textos), -np.inf)
    np.maximum.at(out, np.asarray(dueño), crudo)
    return out


_PALABRAS = re.compile(r"ignore|ignora|assistant:|asistente:", re.I)  # el mock / línea base de palabras clave


def reporte(nombre: str, filas: list[dict], pred: np.ndarray) -> None:
    y = np.array([r["label"] == "attack" for r in filas])
    det = pred[y].mean() if y.any() else float("nan")
    fp = pred[~y].mean() if (~y).any() else float("nan")
    print(f"  {nombre:<16} detección {det:6.1%} ({pred[y].sum()}/{y.sum()})   falsos positivos {fp:6.1%} ({pred[~y].sum()}/{(~y).sum()})")
    por_cat = defaultdict(list)
    for r, s in zip(filas, pred):
        por_cat[(r["label"], r.get("category", ""))].append(s)
    for (lab, cat), v in sorted(por_cat.items()):
        print(f"      {lab:<7} {cat:<22} {np.mean(v):6.1%} marcados (n={len(v)})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train", type=Path, default=config.DATOS / "train.csv")
    ap.add_argument("--val", type=Path, default=config.DATOS / "val.csv")
    ap.add_argument("--modelo", default=config.MODELO, choices=sorted(config.MODELOS))
    ap.add_argument("--fp", type=float, default=0.05, help="falsos positivos máximos en validación para tau_alto")
    ap.add_argument("--fp-bajo", type=float, default=0.20, help="falsos positivos de attack_score solo, para tau_bajo")
    ap.add_argument("--tau-drift", type=float, default=0.75, help="umbral de drift_score (falta un set con tareas para elegirlo)")
    a = ap.parse_args()

    if not a.train.exists():
        a.train = a.val = config.DATOS / "seed.csv"
        print(f"AVISO: no hay data/train.csv; uso {a.train} para entrenar y calibrar (umbrales provisionales).")
    elif not a.val.exists():
        a.val = a.train
        print("AVISO: no hay data/val.csv; calibro sobre el entrenamiento (umbrales optimistas).")
    tr, va = leer(a.train), leer(a.val)
    print(f"entrenamiento: {a.train} ({len(tr)} filas)   validación: {a.val} ({len(va)} filas)   modelo: {a.modelo}")

    v = embed([r["text"] for r in tr], a.modelo)
    es_ataque = np.array([r["label"] == "attack" for r in tr])
    promedio, direccion = ajustar(a.modelo, v[es_ataque], v[~es_ataque])
    p = Parametros(a.modelo, promedio.tolist(), direccion.tolist(), 0.0, 1.0, 1.0, 1.0, a.tau_drift, {})

    crudo = max_coseno(p, [r["text"] for r in va])
    y = np.array([r["label"] == "attack" for r in va])
    leg, ata = crudo[~y], crudo[y]
    # Escala 0-1: 0 = legítimo típico (mediana), 1 = ataque claro (percentil 90) o el legítimo más alto.
    p.escala_min = float(np.median(leg))
    p.escala_max = float(max(np.quantile(ata, 0.9), leg.max()) + 1e-6)
    # tau_alto: el más bajo que deja los falsos positivos en a.fp o menos (sin tarea, el peor caso).
    p.tau_alto = float(p.escalar(np.array([np.quantile(leg, 1 - a.fp, method="higher") + 1e-6]))[0])
    p.tau_bajo = float(p.escalar(np.array([np.quantile(leg, 1 - a.fp_bajo, method="higher") + 1e-6]))[0])
    p.tau_bajo = min(p.tau_bajo, p.tau_alto)

    pred = p.escalar(crudo) >= p.tau_alto
    print(f"\numbrales: tau_alto={p.tau_alto:.3f}  tau_bajo={p.tau_bajo:.3f}  tau_drift={p.tau_drift:.3f}")
    print("validación por texto, sin tarea (solo tau_alto):")
    reporte("guardián", va, pred)
    reporte("palabras clave", va, np.array([bool(_PALABRAS.search(r["text"])) for r in va]))

    p.notas = {
        "train": str(a.train.relative_to(config.RAIZ)), "val": str(a.val.relative_to(config.RAIZ)),
        "n_train": len(tr), "n_val": len(va),
        "deteccion_val": round(float(pred[y].mean()), 4), "falsos_positivos_val": round(float(pred[~y].mean()), 4),
        "fp_objetivo": a.fp,
    }
    print(f"\nguardado en {p.guardar().relative_to(config.RAIZ)}")


if __name__ == "__main__":
    main()
