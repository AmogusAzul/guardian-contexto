"""Contrato 1 (docs/architecture.md). Por ahora es un MOCK.

Cumple la firma y la forma de la respuesta para que bench/ y el resto del equipo
trabajen desde el minuto uno. Algoritmo lo reemplaza por la versión real
(docs/algorithm.md) sin cambiar la firma.
"""

from __future__ import annotations

import re
import time

RETIRADO = "[contenido retirado por el guardián]"

# Solo para el mock: marca oraciones con estas palabras. La versión real usa embeddings.
_PALABRAS_MOCK = ("ignore", "ignora", "assistant:", "asistente:")


def _trozos(texto: str) -> list[str]:
    """Separa en oraciones. La versión real usa ventanas que se solapan."""
    return [t for t in re.split(r"(?<=[.!?])\s+|\n+", texto) if t.strip()]


def check(texto: str, tarea: str | None = None, origen: str = "herramienta") -> tuple[bool, dict]:
    """Revisa un texto antes de que entre al contexto del agente.

    Devuelve (permitido, info). Ver los campos de info en docs/architecture.md.
    """
    inicio = time.perf_counter()
    marcados = []
    limpio = texto
    for trozo in _trozos(texto):
        if any(p in trozo.lower() for p in _PALABRAS_MOCK):
            marcados.append({"texto": trozo, "attack_score": 0.9, "drift_score": None if tarea is None else 0.8})
            limpio = limpio.replace(trozo, RETIRADO)
    peor = max(marcados, key=lambda t: t["attack_score"], default=None)
    info = {
        "texto_limpio": limpio,
        "trozos_marcados": marcados,
        "attack_score": peor["attack_score"] if peor else 0.1,
        "drift_score": peor["drift_score"] if peor else (None if tarea is None else 0.2),
        "latencia_ms": (time.perf_counter() - inicio) * 1000,
        "origen": origen,
    }
    return not marcados, info
