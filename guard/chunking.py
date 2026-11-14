"""Paso 1: parte una salida de herramienta en trozos de texto plano (docs/algorithm.md, "1. Trozos").

Autocontenido: solo biblioteca estándar (y PyYAML cuando se escriba). Nada de embeddings aquí.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Kind = Literal["value", "path", "siblings"]
Format = Literal["json", "yaml", "text"]
PathKey = str | int

WINDOWS = (1, 2, 3)  # oraciones por ventana, en trozos de valor
KEY_WINDOWS = (2, 3)  # claves seguidas por ventana, en trozos de hermanas
MIN_WORDS = 4  # trozos más cortos se descartan
SHORT_VALUE_WORDS = 6  # hasta aquí el valor también entra al trozo de ruta
MAX_CHUNKS = 500  # por encima: solo oraciones sueltas de valores


@dataclass(frozen=True)
class Chunk:
    text: str  # lo que se embebe, sin sintaxis JSON
    kind: Kind
    path: tuple[PathKey, ...]  # ubicación exacta en Document.tree; () para texto plano
    span: tuple[int, int] | None = None  # (inicio, fin) dentro del string; solo "value"
    group: str = ""  # ruta sin índices ("emails[*].body"): define los vecinos
    keys: tuple[str, ...] = ()  # solo "siblings": las claves de la ventana


@dataclass
class Document:
    """La salida ya parseada, lo necesario para reconstruirla en el mismo formato."""

    original: str
    format: Format
    tree: Any  # dict/list parseado, o el string si es texto plano
    json_strings: set[tuple[PathKey, ...]] = field(
        default_factory=set
    )  # strings que traían JSON


def chunk(text: str) -> tuple[Document, list[Chunk]]:
    """Parsea (JSON, YAML o texto), recorre la estructura y devuelve sus trozos."""
    raise NotImplementedError


def format_path(path: tuple[PathKey, ...]) -> str:
    """("emails", 1, "body") -> "$.emails[1].body"."""
    raise NotImplementedError
