"""Paso 6: reconstruye la salida sin los trozos marcados (docs/algorithm.md, "6. Reconstrucción").

Mismo formato que la entrada (JSON, YAML o texto). Los strings que traían JSON vuelven a ser strings.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from guard.chunking import Chunk, Document

PLACEHOLDER = "[contenido retirado por el guardián]"


def rebuild(doc: Document, flagged: Sequence[Chunk]) -> str:
    """El texto limpio: valores -> aviso en su span; rutas -> rama retirada."""
    raise NotImplementedError
