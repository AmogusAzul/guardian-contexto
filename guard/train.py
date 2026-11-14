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
import json
import subprocess
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from guard import attack, decision, drift, embedding, reference, stack
from guard.chunking import Chunk, chunk, label
from guard.drift import ToolCall
from guard.reference import MIN_TABLE, Reference, chunk_class, table

MAX_FP_OUTPUTS = 0.05  # a lo más 5 % de salidas legítimas tocadas


def fp_budget(n_legit: int, new_outputs: bool) -> float:
    """Fracción de legítimas que el umbral puede tocar en las salidas donde se elige.

    Para salidas nuevas (`new_outputs`): con n legítimas, un corte que toca k de ellas toca en
    promedio (k + 1)/(n + 1) de las nuevas (conformal), así que k es el mayor con
    (k + 1)/(n + 1) ≤ 5 %. Con 111 legítimas permite 4 en vez de 5. Para medir a la misma tasa
    en las mismas salidas (lectura 2 de compare) basta el 5 %."""
    if not new_outputs or n_legit == 0:
        return MAX_FP_OUTPUTS
    k = max(0, int(np.floor(MAX_FP_OUTPUTS * (n_legit + 1) + 1e-9)) - 1)
    return k / n_legit + 1e-12


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


@dataclass
class Scored:
    """Una salida de validación con lo que necesita cada método."""

    case: Case
    classes: list[str]
    attack: list[float]
    refs: list[drift.Percentiles]
    comb: list[tuple[float, int] | None]  # (1 − m^k, k) antes de la tabla final


def score_cases(cases: list[Case], model: str) -> list[Scored]:
    ref = reference.load(model)
    out = []
    for c in cases:
        c.vectors = embedding.center(
            embedding.raw([ch.text for ch in c.chunks], model), ref.mean
        )
        refs = drift.percentiles(c.chunks, c.vectors, c.task, c.tool, model)
        out.append(
            Scored(
                c,
                [chunk_class(ch) for ch in c.chunks],
                attack.score(c.chunks, c.vectors, model),
                refs,
                [drift.combine(list(p.values())) for p in refs],
            )
        )
    return out


def k_tables(scored: list[Scored]) -> dict[str, np.ndarray]:
    """Tabla final del desvío por k, con los trozos legítimos de estas salidas."""
    per_k: dict[str, list[float]] = defaultdict(list)
    for s in scored:
        for lab, comb in zip(s.case.labels, s.comb, strict=True):
            if lab == "benign" and comb is not None:
                per_k[f"drift/k{comb[1]}"].append(comb[0])
    return {k: table(np.array(v)) for k, v in per_k.items()}


def drift_with(s: Scored, tables: dict[str, np.ndarray]) -> list[float | None]:
    out: list[float | None] = []
    for comb in s.comb:
        if comb is None:
            out.append(None)
        else:
            t = tables.get(f"drift/k{comb[1]}")
            out.append(
                comb[0] if t is None else min(reference.percentile_in(t, comb[0]), 1.0)
            )
    return out


def rates(flags: list[tuple[Case, list[bool]]]) -> tuple[float, float]:
    """(salidas atacadas atrapadas con un trozo de ataque, salidas legítimas tocadas)."""
    caught = [
        any(f and lab == "attack" for f, lab in zip(F, c.labels))
        for c, F in flags
        if c.attacked
    ]
    fp = [any(F) for c, F in flags if not c.attacked]
    return float(np.mean(caught)), float(np.mean(fp))


# ---------------------------------------------------------------- métodos
# Cada uno ajusta sus piezas (tablas, pesos) con `scored` y elige sus umbrales con `tune`
# (por defecto las mismas salidas). Devuelve cómo marcar otras salidas (flag) y lo ajustado.


def best_single(
    scored: list[Scored], risk: Callable[[Scored], np.ndarray], new_outputs: bool = True
) -> float:
    """Umbral único que más salidas atacadas atrapa dentro del presupuesto de fp_budget.

    Candidatos: justo por encima del máximo de cada salida legítima (el corte exacto)."""
    rs = [(s, risk(s)) for s in scored]
    budget = fp_budget(sum(not s.case.attacked for s in scored), new_outputs)
    out_max = sorted({float(r.max(initial=0.0)) for s, r in rs if not s.case.attacked})
    best = (-1.0, 1.0, above(out_max[-1]) if out_max else 1.0)
    for m in out_max:
        tau = above(m)
        caught, fp = rates([(s.case, list(r >= tau)) for s, r in rs])
        if fp <= budget and (caught, -fp) > (best[0], -best[1]):
            best = (caught, fp, tau)
    return float(best[2])


def rule_method(tables_from: str):
    """Regla de dos umbrales; la tabla final del desvío sale de train o de estas salidas."""

    def fit(
        scored: list[Scored],
        train_tables: dict[str, np.ndarray],
        tune: list[Scored] | None = None,
    ):
        tables = train_tables if tables_from == "train" else k_tables(scored)
        rows = [(s.case, s.attack, drift_with(s, tables)) for s in tune or scored]
        t, _, _ = grid(rows, new_outputs=tune is None)

        def flag(s: Scored) -> list[bool]:
            return [
                decision.flags(a, d, t) for a, d in zip(s.attack, drift_with(s, tables))
            ]

        return flag, {"thresholds": t, "tables": tables}

    return fit


def attack_only(
    scored: list[Scored],
    train_tables: dict[str, np.ndarray],
    tune: list[Scored] | None = None,
):
    tau = best_single(
        tune or scored, lambda s: np.array(s.attack), new_outputs=tune is None
    )

    def flag(s: Scored) -> list[bool]:
        return [a >= tau for a in s.attack]

    return flag, {"thresholds": {"tau_high": tau}}


def stack_method(
    scored: list[Scored],
    train_tables: dict[str, np.ndarray],
    tune: list[Scored] | None = None,
):
    xs, ys = [], []
    for s in scored:
        x = stack.features(s.case.chunks, s.attack, s.refs)
        for row, lab in zip(x, s.case.labels):
            if lab is not None:
                xs.append(row)
                ys.append(1.0 if lab == "attack" else 0.0)
    w = stack.fit(np.array(xs), np.array(ys))

    def risk(s: Scored) -> np.ndarray:
        return stack.risk(s.case.chunks, s.attack, s.refs, w)

    tau = best_single(tune or scored, risk, new_outputs=tune is None)

    def flag(s: Scored) -> list[bool]:
        return list(risk(s) >= tau)

    return flag, {"tau_stack": tau, "weights": w}


METHODS = {
    "solo ataque": attack_only,
    "regla, tabla k de train": rule_method("train"),
    "regla, tabla k de val": rule_method("val"),
    "logística": stack_method,
}

Rates = tuple[float, float]


def halves(scored: list[Scored], seed: int = 0) -> list[list[Scored]]:
    """Dos mitades al azar de las salidas de validación."""
    order = np.random.default_rng(seed).permutation(len(scored))
    return [[scored[i] for i in order[0::2]], [scored[i] for i in order[1::2]]]


def compare(
    scored: list[Scored], train_tables: dict[str, np.ndarray], splits: int = 1
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Validación cruzada en dos mitades, con dos lecturas, sobre `splits` particiones al azar.

    1. Todo en A (piezas y umbrales), medido en B: lo que pasaría en ejecución.
    2. Piezas en A, umbrales elegidos en B y medido en B: todos los métodos quedan a lo más
       en 5 % de legítimas tocadas, así se comparan a la misma tasa. Es la lectura que elige.
    La diferencia entre las dos es lo que se pierde al trasladar el umbral. Devuelve, por
    método y lectura, una fila (atrapadas, tocadas) por partición, promedio de las dos vueltas.
    """
    results: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for name, fit in METHODS.items():
        r1, r2 = [], []
        for seed in range(splits):
            hs = halves(scored, seed)
            a1, a2 = [], []
            for a, b in ((0, 1), (1, 0)):
                flag, _ = fit(hs[a], train_tables)
                a1.append(rates([(s.case, flag(s)) for s in hs[b]]))
                flag, _ = fit(hs[a], train_tables, tune=hs[b])
                a2.append(rates([(s.case, flag(s)) for s in hs[b]]))
            r1.append(np.mean(a1, axis=0))
            r2.append(np.mean(a2, axis=0))
        results[name] = (np.array(r1), np.array(r2))
    return results


def auc(pos: list[float], neg: list[float]) -> float:
    """Probabilidad de que un ataque puntúe más que un legítimo."""
    if not pos or not neg:
        return float("nan")
    ranks = np.argsort(np.argsort(np.array(pos + neg))) + 1
    return float(
        (ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2)
        / (len(pos) * len(neg))
    )


def above(x: float) -> float:
    return float(np.nextafter(float(x), np.inf))


def grid(
    scored: list, new_outputs: bool = True
) -> tuple[dict[str, float], float, float]:
    """Umbrales que más salidas atacadas atrapan dentro del presupuesto de fp_budget."""
    best: tuple[float, float, dict[str, float]] = (
        -1.0,
        1.0,
        dict(reference.DEFAULT_THRESHOLDS),
    )
    benign = [s for s in scored if not s[0].attacked]
    attacked = [s for s in scored if s[0].attacked]
    budget = fp_budget(len(benign), new_outputs)
    # Candidatos sacados de los mismos datos: el máximo de ataque de las salidas legítimas
    # (tau_high), el ataque de los trozos legítimos (tau_low) y valores fijos de desvío.
    out_max = [max(A, default=0.0) for _, A, _ in benign]
    chunk_att = [a for _, A, _ in benign for a in A]
    # Cada candidato va justo por encima del valor (con `>=`, un umbral igual al máximo de una
    # salida legítima la tocaría). Para tau_high, todos los máximos de la cola alta: los cortes
    # exactos, como en best_single.
    highs = sorted({above(m) for m in out_max if m >= np.quantile(out_max, 0.9)})
    lows = sorted(
        {above(np.quantile(chunk_att, q)) for q in (0.8, 0.9, 0.95, 0.98, 0.99)}
    )
    # lo = hi apaga la rama del desvío: siempre queda una opción que cumple el 5 %.
    combos = [
        (hi, lo, dr)
        for hi in highs
        for lo in [*lows, hi]
        if lo <= hi
        for dr in (0.5, 0.7, 0.8, 0.9, 0.95, 0.98)
    ]
    for hi, lo, dr in combos:
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
        if fp <= budget and (caught, -fp) > (best[0], -best[1]):
            best = (float(caught), float(fp), t)
    return best[2], best[0], best[1]


def report(scored: list[Scored]) -> None:
    rng = np.random.default_rng(0)
    benign = np.array(
        [
            s.case.vectors[i]
            for s in scored
            for i, lab in enumerate(s.case.labels)
            if lab == "benign"
        ]
    )
    idx = rng.integers(0, len(benign), size=(2000, 2))
    mean_cos = np.mean(np.sum(benign[idx[:, 0]] * benign[idx[:, 1]], axis=1))
    print(f"centrado: coseno promedio entre legítimos al azar = {mean_cos:.3f}")
    per: dict[str, tuple[list[float], list[float]]] = defaultdict(lambda: ([], []))
    for s in scored:
        for cls, a, lab in zip(s.classes, s.attack, s.case.labels):
            if lab is not None:
                per[cls][0 if lab == "attack" else 1].append(a)
    print("separación (AUC del ataque por clase, en validación):")
    for cls, (pos, neg) in sorted(per.items()):
        print(
            f"  {cls:<12} AUC = {auc(pos, neg):.3f}   ataques {len(pos):>4}   legítimos {len(neg):>5}"
        )


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
    ap.add_argument(
        "--splits", type=int, default=10, help="particiones al azar de validación"
    )
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
    report(scored)
    train_tables = {k: v for k, v in ref.tables.items() if k.startswith("drift/k")}
    results = compare(scored, train_tables, a.splits)
    n = len(halves(scored)[0])
    print(
        f"métodos (dos mitades de ~{n} salidas, la mitad legítimas; {a.splits} particiones; promedio ± desviación):"
    )
    print(
        f"  {'':<24} {'umbral de A, medido en B':>32}   {'umbral de B (misma tasa)':>32}   traslado"
    )

    def cell(r: np.ndarray) -> str:
        (c, f), (sc, sf) = r.mean(axis=0), r.std(axis=0)
        return f"atrapadas {c:4.0%} ±{sc:3.0%} tocadas {f:3.0%} ±{sf:3.0%}"

    for name, (r1, r2) in results.items():
        gap = r1.mean(axis=0) - r2.mean(axis=0)
        print(f"  {name:<24} {cell(r1)}   {cell(r2)}   {gap[0]:+.0%} / {gap[1]:+.0%}")
    best = max(results, key=lambda n: results[n][1][:, 0].mean())
    print(
        f"mejor a la misma tasa: {best} (la versión 1 usa igual solo ataque; ver docs/algorithm.md)"
    )
    chosen = "solo ataque"  # versión 1: el desvío no decide
    print(f"elegido: {chosen}; se ajusta con toda la validación")

    flag, fitted = METHODS[chosen](scored, train_tables)
    ref.tables = {k: v for k, v in ref.tables.items() if not k.startswith("drift/k")}
    ref.tables |= fitted.get("tables") or k_tables(scored)
    ref.method = "stack" if chosen == "logística" else "rule"
    ref.thresholds = dict(reference.DEFAULT_THRESHOLDS) | fitted.get("thresholds", {})
    if chosen == "logística":
        ref.thresholds["tau_stack"] = fitted["tau_stack"]
        ref.stack = fitted["weights"]
    elif chosen == "solo ataque":
        ref.thresholds |= {"tau_low": 2.0, "tau_drift": 2.0}  # el desvío no decide
    ref.save(reference.artifact_path(a.model))
    reference.load.cache_clear()
    caught, fp = rates([(s.case, flag(s)) for s in scored])
    print(
        f"en toda la validación (optimista): atrapadas {caught:.0%}, legítimas tocadas {fp:.0%}"
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
