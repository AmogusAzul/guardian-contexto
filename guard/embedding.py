"""Paso 2: embeddings de los trozos (docs/algorithm.md, "2. Embeddings").

Modelo pequeño en CPU, cargado una vez. Cada texto distinto se embebe una sola vez, y un caché
guarda los recientes (pedido, llamada y rutas se repiten entre llamadas). Los vectores salen
normalizados y centrados con el promedio de los datos de referencia.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

from guard import reference

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # comparación con otros: sprint 2
CACHE_SIZE = 4096
_cache: OrderedDict[str, np.ndarray] = OrderedDict()


@lru_cache(maxsize=1)
def _model(name: str) -> SentenceTransformer:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(name, device="cpu")


def raw(texts: Sequence[str], model: str = MODEL) -> np.ndarray:
    """Normalizados, sin centrar. Una fila por texto, en el mismo orden."""
    missing = list(dict.fromkeys(t for t in texts if t not in _cache))
    if missing:
        vecs = _model(model).encode(missing, batch_size=64, normalize_embeddings=True)
        for t, v in zip(missing, vecs, strict=True):
            _cache[t] = np.asarray(v, dtype=np.float32)
    for t in texts:
        _cache.move_to_end(t)
    while len(_cache) > CACHE_SIZE:
        _cache.popitem(last=False)
    if not texts:
        return np.zeros(
            (0, _model(model).get_embedding_dimension() or 0), dtype=np.float32
        )
    return np.stack([_cache[t] for t in texts])


def center(vectors: np.ndarray, mean: np.ndarray) -> np.ndarray:
    """Restar el promedio y volver a normalizar: saca a los vectores del “cono” estrecho."""
    v = vectors - mean
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    return v / np.where(norms == 0, 1.0, norms)


def embed(texts: Sequence[str], model: str = MODEL) -> np.ndarray:
    """Normalizados y centrados: lo que usan attack y drift."""
    return center(raw(texts, model), reference.load(model).mean)
