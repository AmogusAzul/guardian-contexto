"""Arma los datos de referencia y elige los umbrales (docs/algorithm.md, pasos 2 a 5).

    python -m guard.train          # data/mcp_train.jsonl -> referencia; data/mcp_val.jsonl -> umbrales

1. Trocea cada salida y etiqueta cada trozo contra `injected_text` (chunking.label).
2. Promedio para centrar: el de los trozos, equilibrado por fuente.
3. Dirección de ataque: promedio de ataques − promedio de legítimos, también por fuente.
4. Tablas de percentiles con los trozos legítimos: ataque por clase, desvío por referencia y clase.
5. En validación: pruebas del paso y búsqueda en rejilla de los tres umbrales, por salida.

Nunca usar textos de AgentDojo aquí.
"""

from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from guard import attack, decision, drift, embedding, reference
from guard.chunking import Chunk, chunk, label
from guard.drift import ToolCall
from guard.reference import MIN_TABLE, Reference, chunk_class, table

MAX_FP_OUTPUTS = 0.05  # a lo más 5 % de salidas legítimas tocadas


@dataclass
class Case:
    source: str
    task: str
    tool: ToolCall
    chunks: list[Chunk]
    labels: list[str | None]
    attacked: bool
    vectors: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))  # centrados


def load_cases(path: Path) -> list[Case]:
    cases = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            _, chunks = chunk(r["mcp_response"]["result"]["content"][0]["text"])
            params = r["mcp_request"]["params"]
            cases.append(
                Case(
                    source=r["source"],
                    task=r["prompt"],
                    tool=ToolCall(params["name"], "", params.get("arguments") or {}),
                    chunks=chunks,
                    labels=[label(c, r["injected_text"]) for c in chunks],
                    attacked=bool(r["injected_text"]),
                )
            )
    return cases


def by_source_mean(vectors: list[np.ndarray], sources: list[str]) -> np.ndarray:
    """Promedio de los promedios de cada fuente: ninguna fuente decide sola."""
    groups: dict[str, list[np.ndarray]] = defaultdict(list)
    for v, s in zip(vectors, sources, strict=True):
        groups[s].append(v)
    return np.mean([np.mean(g, axis=0) for g in groups.values()], axis=0)


def build(cases: list[Case], model: str) -> Reference:
    for c in cases:
        c.vectors = embedding.raw([ch.text for ch in c.chunks], model)
    pairs = [(c, i) for c in cases for i, lab in enumerate(c.labels) if lab is not None]
    mean = by_source_mean(
        [c.vectors[i] for c, i in pairs], [c.source for c, _ in pairs]
    )
    for c in cases:
        c.vectors = embedding.center(c.vectors, mean)

    def side(lab: str) -> np.ndarray:
        sel = [(c, i) for c, i in pairs if c.labels[i] == lab]
        return by_source_mean(
            [c.vectors[i] for c, i in sel], [c.source for c, _ in sel]
        )

    d = side("attack") - side("benign")
    d /= np.linalg.norm(d)

    # Tablas con los trozos legítimos. Se escriben antes de calcular el desvío: embedding.embed
    # centra pedido y llamada con el promedio de la referencia guardada.
    ref = Reference(
        model=model, mean=mean, direction=d, tables={}, data=_data_version()
    )
    ref.save(reference.artifact_path(model))
    reference.load.cache_clear()

    values: dict[str, list[float]] = defaultdict(list)
    for c in cases:
        raws = drift.raw_cosines(c.chunks, c.vectors, c.task, c.tool, model)
        a = attack.raw(c.vectors, d)
        for i, ch in enumerate(c.chunks):
            if c.labels[i] != "benign":
                continue
            cls, kind = chunk_class(ch), ch.kind
            values[f"attack/{cls}"].append(float(a[i]))
            values[f"attack/{kind}"].append(float(a[i]))
            for r in drift.REFERENCES:
                if (x := raws[r][i]) is not None:
                    values[f"drift-{r}/{cls}"].append(x)
                    values[f"drift-{r}/{kind}"].append(x)
    ref.tables = {
        k: table(np.array(v))
        for k, v in values.items()
        if len(v) >= MIN_TABLE or k.split("/")[1] in ("value", "path")
    }
    ref.save(reference.artifact_path(model))
    reference.load.cache_clear()

    # Última tabla del desvío, por k: 1 − m^k de los legítimos de entrenamiento.
    per_k: dict[str, list[float]] = defaultdict(list)
    for c in cases:
        raws = drift.raw_cosines(c.chunks, c.vectors, c.task, c.tool, model)
        for i, value in enumerate(
            drift.score(c.chunks, c.vectors, c.task, c.tool, model)
        ):
            if c.labels[i] == "benign" and value is not None:
                k = sum(raws[r][i] is not None for r in drift.REFERENCES)
                per_k[f"drift/k{k}"].append(value)
    ref.tables |= {k: table(np.array(v)) for k, v in per_k.items()}
    ref.save(reference.artifact_path(model))
    reference.load.cache_clear()
    return ref


def score_cases(
    cases: list[Case], model: str
) -> list[tuple[Case, list[float], list[float | None]]]:
    ref = reference.load(model)
    out = []
    for c in cases:
        v = embedding.center(
            embedding.raw([ch.text for ch in c.chunks], model), ref.mean
        )
        c.vectors = v
        out.append(
            (
                c,
                attack.score(c.chunks, v, model),
                drift.score(c.chunks, v, c.task, c.tool, model),
            )
        )
    return out


def auc(pos: list[float], neg: list[float]) -> float:
    """Probabilidad de que un ataque puntúe más que un legítimo."""
    if not pos or not neg:
        return float("nan")
    ranks = np.argsort(np.argsort(np.array(pos + neg))) + 1
    return float(
        (ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2)
        / (len(pos) * len(neg))
    )


def grid(scored: list) -> tuple[dict[str, float], float, float]:
    """Umbrales que más salidas atacadas atrapan con a lo más 5 % de salidas legítimas tocadas."""
    best: tuple[float, float, dict[str, float]] = (
        -1.0,
        1.0,
        dict(reference.DEFAULT_THRESHOLDS),
    )
    benign = [s for s in scored if not s[0].attacked]
    attacked = [s for s in scored if s[0].attacked]
    # Candidatos sacados de los mismos datos: el máximo de ataque de cada salida legítima
    # (tau_high), el ataque de los trozos legítimos (tau_low) y valores fijos de desvío.
    out_max = [max(A, default=0.0) for _, A, _ in benign]
    chunk_att = [a for _, A, _ in benign for a in A]
    highs = sorted(
        {float(np.quantile(out_max, q)) for q in (0.9, 0.93, 0.95, 0.97, 0.99, 1.0)}
    )
    lows = sorted(
        {float(np.quantile(chunk_att, q)) for q in (0.8, 0.9, 0.95, 0.98, 0.99)}
    )
    for hi, lo, dr in itertools.product(highs, lows, (0.5, 0.7, 0.8, 0.9, 0.95, 0.98)):
        if lo > hi:
            continue
        t = {"tau_high": hi, "tau_low": lo, "tau_drift": dr}
        fp = np.mean(
            [any(decision.flags(a, d, t) for a, d in zip(A, D)) for _, A, D in benign]
        )
        caught = np.mean(
            [
                any(
                    decision.flags(a, d, t) and c.labels[i] == "attack"
                    for i, (a, d) in enumerate(zip(A, D))
                )
                for c, A, D in attacked
            ]
        )
        if fp <= MAX_FP_OUTPUTS and (caught, -fp) > (best[0], -best[1]):
            best = (float(caught), float(fp), t)
    return best[2], best[0], best[1]


def report(scored: list, model: str) -> None:
    rng = np.random.default_rng(0)
    benign_vecs = np.array(
        [
            c.vectors[i]
            for c, _, _ in scored
            for i, lab in enumerate(c.labels)
            if lab == "benign"
        ]
    )
    idx = rng.integers(0, len(benign_vecs), size=(2000, 2))
    print(
        f"centrado: coseno promedio entre legítimos al azar = {np.mean(np.sum(benign_vecs[idx[:, 0]] * benign_vecs[idx[:, 1]], axis=1)):.3f}"
    )

    per: dict[str, tuple[list[float], list[float]]] = defaultdict(lambda: ([], []))
    deciles: dict[int, list[float]] = defaultdict(list)
    for c, A, D in scored:
        raws = drift.raw_cosines(c.chunks, c.vectors, c.task, c.tool, model)
        for i, ch in enumerate(c.chunks):
            lab = c.labels[i]
            if lab is None:
                continue
            per[chunk_class(ch)][0 if lab == "attack" else 1].append(A[i])
            if lab == "benign" and D[i] is not None:
                k = sum(raws[r][i] is not None for r in drift.REFERENCES)
                deciles[k].append(D[i])
    print("separación (AUC del ataque por clase, en validación):")
    for cls, (pos, neg) in sorted(per.items()):
        print(
            f"  {cls:<12} AUC = {auc(pos, neg):.3f}   ataques {len(pos):>4}   legítimos {len(neg):>5}"
        )
    print("calibración del desvío en legítimos (debería ser ~10 % por décimo):")
    for k, v in sorted(deciles.items()):
        h = np.histogram(v, bins=10, range=(0, 1))[0] / max(1, len(v))
        print(f"  k={k}  n={len(v):>5}  " + " ".join(f"{x:.0%}".rjust(4) for x in h))


def _data_version() -> str:
    try:
        commit = subprocess.run(
            ["git", "log", "-1", "--format=%h", "--", "data"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    except OSError:
        commit = ""
    return f"data/mcp_train.jsonl @ {commit or '?'}"


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Arma los datos de referencia y elige los umbrales"
    )
    ap.add_argument("--train", type=Path, default=Path("data/mcp_train.jsonl"))
    ap.add_argument("--val", type=Path, default=Path("data/mcp_val.jsonl"))
    ap.add_argument("--model", default=embedding.MODEL)
    a = ap.parse_args()

    t0 = time.perf_counter()
    train = load_cases(a.train)
    ref = build(train, a.model)
    print(
        f"referencia: {len(train)} salidas, {sum(len(c.chunks) for c in train)} trozos, "
        f"{len(ref.tables)} tablas, {time.perf_counter() - t0:.0f} s"
    )

    val = load_cases(a.val)
    scored = score_cases(val, a.model)
    report(scored, a.model)
    t, caught, fp = grid(scored)
    ref.thresholds = t
    ref.save(reference.artifact_path(a.model))
    print(
        f"umbrales: {t}  ->  salidas atacadas atrapadas {caught:.0%}, legítimas tocadas {fp:.0%}"
    )

    embedding._cache.clear()
    times = []
    for c in val[:100]:
        s = time.perf_counter()
        embedding.raw([ch.text for ch in c.chunks], a.model)
        times.append((time.perf_counter() - s) * 1000)
        embedding._cache.clear()
    print(
        f"latencia de embeber una salida: mediana {np.median(times):.0f} ms, p95 {np.percentile(times, 95):.0f} ms"
    )
    print(f"guardado en {reference.artifact_path(a.model)}")


if __name__ == "__main__":
    main()
