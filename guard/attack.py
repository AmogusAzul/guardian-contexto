"""Paso 3: attack_score de cada trozo (docs/algorithm.md, "3. attack_score").

Parecido con la dirección de ataque, convertido a percentil de los trozos legítimos del mismo tipo.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

    from guard.chunking import Chunk


def score(chunks: Sequence[Chunk], vectors: NDArray[np.float32]) -> list[float]:
    """Un puntaje en [0, 1] por trozo."""
    raise NotImplementedError
