"""Paso 5: qué trozos se retiran (docs/algorithm.md, "5. Decisión").

Retirar si attack >= tau_high, o si attack >= tau_low y drift >= tau_drift.
Los umbrales se eligen en validación, por salida completa.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from guard.chunking import Chunk


def decide(
    chunks: Sequence[Chunk],
    attack_scores: Sequence[float],
    drift_scores: Sequence[float | None],
) -> list[int]:
    """Índices de los trozos marcados, sin solapes."""
    raise NotImplementedError
