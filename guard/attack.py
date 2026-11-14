"""Paso 3: attack_score de cada trozo (docs/algorithm.md, "3. attack_score").

raw = coseno con la dirección de ataque (promedio de ataques − promedio de legítimos).
attack = percentil de raw entre los trozos legítimos de su clase: 0,99 = se proyecta hacia
"ataque" más que el 99 % de los legítimos de su tipo y tamaño.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from guard import embedding, reference
from guard.chunking import Chunk


def raw(vectors: np.ndarray, direction: np.ndarray) -> np.ndarray:
    return vectors @ direction


def score(
    chunks: Sequence[Chunk], vectors: np.ndarray, model: str = embedding.MODEL
) -> list[float]:
    """Un puntaje en [0, 1] por trozo."""
    ref = reference.load(model)
    out = []
    for c, r in zip(chunks, raw(vectors, ref.direction), strict=True):
        p = ref.percentile("attack", reference.chunk_class(c), float(r))
        out.append(0.0 if p is None else p)
    return out
