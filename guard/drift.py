"""Paso 4: drift_score de cada trozo (docs/algorithm.md, "4. drift_score").

Qué tan poco encaja el trozo con sus referencias (pedido, llamada a la herramienta, vecinos):
cada coseno pasa a percentil de los legítimos y drift = 1 - max(p)^k.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

    from guard.chunking import Chunk

MIN_PEERS = 3  # con menos vecinos, no hay referencia de vecinos


@dataclass(frozen=True)
class ToolCall:
    """La llamada que produjo la salida: una de las referencias del desvío."""

    name: str
    description: str = ""
    arguments: Mapping[str, Any] = field(default_factory=dict)


def score(
    chunks: Sequence[Chunk],
    vectors: NDArray[np.float32],
    task: str | None,
    tool: ToolCall | None,
) -> list[float | None]:
    """Un puntaje en [0, 1] por trozo; None si el trozo no tiene ninguna referencia."""
    raise NotImplementedError
