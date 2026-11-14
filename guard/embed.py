"""Paso 2 de docs/algorithm.md: embeddings normalizados, con el modelo cargado una sola vez."""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from guard import config


@lru_cache(maxsize=None)
def _modelo(nombre: str):
    libreria, ruta = config.MODELOS[nombre]
    if libreria == "model2vec":
        from model2vec import StaticModel

        return StaticModel.from_pretrained(ruta)
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(ruta, device="cpu")


def embed(textos: list[str], modelo: str = config.MODELO) -> np.ndarray:
    """Matriz (n, d) de vectores de norma 1."""
    if not textos:
        return np.zeros((0, 1), dtype=np.float32)
    v = np.asarray(_modelo(modelo).encode(list(textos)), dtype=np.float32)
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)
