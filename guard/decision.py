"""Paso 5: qué trozos se retiran (docs/algorithm.md, "5. Decisión").

Retirar si attack >= tau_high, o si attack >= tau_low y drift >= tau_drift: el ataque decide solo
cuando es claro; el desvío solo resuelve la zona gris y nunca retira nada por sí mismo.
Con `method = "stack"` (si ganó en validación) decide una regresión logística sobre los
percentiles (guard/stack.py) con un solo umbral. Entre ventanas que se solapan gana la más
corta: una oración maliciosa no arrastra a sus vecinas.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from guard import embedding, reference, stack
from guard.chunking import Chunk


def flags(attack: float, drift: float | None, t: Mapping[str, float]) -> bool:
    if attack >= t["tau_high"]:
        return True
    return attack >= t["tau_low"] and drift is not None and drift >= t["tau_drift"]


def mask(
    chunks: Sequence[Chunk],
    attack_scores: Sequence[float],
    drift_scores: Sequence[float | None],
    refs: Sequence[Mapping[str, float | None]] | None,
    ref: reference.Reference,
    thresholds: Mapping[str, float] | None = None,
) -> list[bool]:
    """Qué trozos pasan el umbral, antes de resolver solapes."""
    t = thresholds or ref.thresholds
    if ref.method == "stack" and refs is not None and len(ref.stack):
        classes = [reference.chunk_class(c) for c in chunks]
        risk = stack.predict(stack.features(classes, attack_scores, refs), ref.stack)
        return [bool(r >= t["tau_stack"]) for r in risk]
    return [flags(a, d, t) for a, d in zip(attack_scores, drift_scores, strict=True)]


def decide(
    chunks: Sequence[Chunk],
    attack_scores: Sequence[float],
    drift_scores: Sequence[float | None],
    refs: Sequence[Mapping[str, float | None]] | None = None,
    thresholds: Mapping[str, float] | None = None,
    model: str = embedding.MODEL,
) -> list[int]:
    """Índices de los trozos marcados, sin solapes."""
    ref = reference.load(model)
    m = mask(chunks, attack_scores, drift_scores, refs, ref, thresholds)
    flagged = [i for i, f in enumerate(m) if f]
    kept: list[int] = []
    for i in sorted(flagged, key=lambda i: _length(chunks[i])):
        c = chunks[i]
        if c.span is None or not any(
            chunks[j].path == c.path
            and (s := chunks[j].span) is not None
            and s[0] < c.span[1]
            and c.span[0] < s[1]
            for j in kept
        ):
            kept.append(i)
    return sorted(kept)


def _length(c: Chunk) -> int:
    return (c.span[1] - c.span[0]) if c.span else 0
