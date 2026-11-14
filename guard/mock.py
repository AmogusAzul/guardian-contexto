"""Mock del Contrato 1 (docs/architecture.md): palabras clave, sin dependencias.

Se usa con GUARD_MOCK=1. Cumple la firma y la forma de la respuesta para que bench/ y el resto del equipo
trabajen sin instalar el modelo. La versión real es check() en guard/__init__.py
(docs/algorithm.md), con la misma firma.
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


def check(
    texto: str,
    tarea: str | None = None,
    origen: str = "herramienta",
    herramienta: object | None = None,
) -> tuple[bool, dict]:
    """Revisa un texto antes de que entre al contexto del agente.

    Devuelve (permitido, info). Ver los campos de info en docs/architecture.md.
    El mock ignora `herramienta`.
    """
    del herramienta
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
