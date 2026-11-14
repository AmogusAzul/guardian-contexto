"""Guardián de contexto: revisa las salidas de herramientas antes de que entren al contexto del LLM.

check() sigue el flujo de docs/algorithm.md, un módulo por paso:

    chunking -> embedding -> attack -> decision -> rebuild

Versión 1: decide solo el ataque. drift.py, stack.py y la comparación de guard.train quedan
para la versión 2.

GUARD_MOCK=1 usa el mock de palabras clave (guard/mock.py, sin dependencias).
"""

from __future__ import annotations

import os
import time

from guard.toolcall import ToolCall

ORIGENES = ("herramienta", "manifiesto", "usuario")


def check(
    texto: str,
    tarea: str | None = None,
    origen: str = "herramienta",
    herramienta: ToolCall | None = None,
) -> tuple[bool, dict]:
    """Contrato 1 (docs/architecture.md): devuelve (permitido, info)."""
    if origen not in ORIGENES:
        raise ValueError(f"origen desconocido: {origen!r}; usar uno de {ORIGENES}")
    # Importación aquí: con GUARD_MOCK=1 el paquete se importa sin numpy, PyYAML ni el modelo.
    from guard import attack, chunking, decision, embedding, rebuild

    inicio = time.perf_counter()

    doc, chunks = chunking.chunk(texto)
    vectors = embedding.embed([c.text for c in chunks])
    attack_scores = attack.score(chunks, vectors)
    # Versión 1: decide solo el ataque. El desvío (guard/drift.py) queda para la versión 2:
    # no se calcula, `tarea` y `herramienta` se aceptan pero no se usan y drift_score es None.
    del tarea, herramienta
    drift_scores: list[float | None] = [None] * len(chunks)
    flagged = decision.decide(
        chunks, attack_scores, drift_scores, thresholds=_ATTACK_ONLY | _thresholds()
    )
    texto_limpio = rebuild.rebuild(doc, [chunks[i] for i in flagged])

    marcados = [
        {
            "texto": chunks[i].text,
            "tipo": chunks[i].kind,
            "ruta": chunking.format_path(chunks[i].path),
            "attack_score": attack_scores[i],
            "drift_score": drift_scores[i],
        }
        for i in flagged
    ]
    peor = max(range(len(chunks)), key=lambda i: attack_scores[i], default=None)
    info = {
        "texto_limpio": texto_limpio,
        "trozos_marcados": marcados,
        "attack_score": attack_scores[peor] if peor is not None else 0.0,
        "drift_score": drift_scores[peor] if peor is not None else None,
        "latencia_ms": (time.perf_counter() - inicio) * 1000,
        "origen": origen,
    }
    return not flagged, info


_ATTACK_ONLY = {"tau_low": 2.0, "tau_drift": 2.0}  # la regla sin la rama del desvío


def _thresholds() -> dict[str, float]:
    from guard import embedding, reference

    return {"tau_high": reference.load(embedding.MODEL).thresholds["tau_high"]}


def describe() -> dict:
    """Qué guardián está corriendo, para anotar en los resultados (bench/)."""
    if os.environ.get("GUARD_MOCK") == "1":
        return {"modelo": "mock"}
    from guard import embedding, reference

    ref = reference.load(embedding.MODEL)
    return {
        "modelo": ref.model,
        "decision": "solo ataque",
        "tau_alto": ref.thresholds["tau_high"],
        "datos": ref.data,
    }


def warmup() -> None:
    """Carga el modelo y la referencia (unos 15 s la primera vez) antes de medir latencias."""
    if os.environ.get("GUARD_MOCK") != "1":
        check("Warm up the guard before measuring.")


if os.environ.get("GUARD_MOCK") == "1":
    from guard.mock import check

__all__ = ["ORIGENES", "ToolCall", "check", "describe", "warmup"]
