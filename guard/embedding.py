"""Paso 2: embeddings de los trozos (docs/algorithm.md, "2. Embeddings").

Modelo pequeño en CPU, cargado una vez. Vectores normalizados y centrados. Cada texto distinto
se embebe una sola vez.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # comparación con otros: sprint 2
ARTIFACTS = (
    "guard/artifacts"  # <modelo>.npz: promedio, dirección de ataque, percentiles
)


def embed(texts: Sequence[str]) -> NDArray[np.float32]:
    """Una fila por texto, en el mismo orden: normalizada y centrada."""
    raise NotImplementedError
