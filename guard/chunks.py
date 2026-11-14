"""Paso 1 de docs/algorithm.md: oraciones y ventanas que se solapan, con sus posiciones en el texto."""

from __future__ import annotations

import re
from dataclasses import dataclass

from guard import config

_FIN = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass(frozen=True)
class Trozo:
    texto: str
    primera: int  # índice de la primera oración
    ultima: int   # índice de la última oración (incluida)


def oraciones(texto: str) -> list[tuple[int, int]]:
    """Devuelve (inicio, fin) de cada oración en `texto`."""
    spans, pos = [], 0
    for m in list(_FIN.finditer(texto)) + [None]:
        fin = m.start() if m else len(texto)
        spans.extend(_partir_larga(texto, pos, fin))
        pos = m.end() if m else len(texto)
    return spans


def _partir_larga(texto: str, ini: int, fin: int) -> list[tuple[int, int]]:
    """Recorta espacios y parte oraciones de más de MAX_PALABRAS_ORACION palabras."""
    palabras = list(re.finditer(r"\S+", texto[ini:fin]))
    if not palabras:
        return []
    n = config.MAX_PALABRAS_ORACION
    return [
        (ini + grupo[0].start(), ini + grupo[-1].end())
        for grupo in (palabras[i : i + n] for i in range(0, len(palabras), n))
    ]


def trozos(texto: str, spans: list[tuple[int, int]]) -> list[Trozo]:
    """Ventanas de 1 a 3 oraciones (más el texto completo si es corto), sin las de menos de 4 palabras."""
    salida: dict[tuple[int, int], Trozo] = {}
    for k in config.VENTANAS:
        for i in range(len(spans) - k + 1):
            salida[(i, i + k - 1)] = Trozo(texto[spans[i][0] : spans[i + k - 1][1]], i, i + k - 1)
    if spans and len(texto.split()) <= config.MAX_PALABRAS_TEXTO_CORTO:
        salida.setdefault((0, len(spans) - 1), Trozo(texto[spans[0][0] : spans[-1][1]], 0, len(spans) - 1))
    return [t for t in salida.values() if len(t.texto.split()) >= config.MIN_PALABRAS]
