"""Guardián de contexto: revisa las salidas de herramientas antes de que entren al contexto del LLM.

check() sigue el flujo de docs/algorithm.md, un módulo por paso:

    chunking -> embedding -> attack + drift -> decision -> rebuild

Versión 2: decide la combinación aprendida (guard/stack.py) sobre el ataque y el desvío, o la
regla que haya elegido guard.train (queda en el archivo de referencia, `method`).

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
    from guard import attack, chunking, decision, drift, embedding, rebuild

    inicio = time.perf_counter()

    doc, chunks = chunking.chunk(texto)
    vectors = embedding.embed([c.text for c in chunks])
    attack_scores = attack.score(chunks, vectors)
    # El mensaje del usuario es la tarea: medir su desvío contra sí mismo no tiene sentido.
    refs = drift.percentiles(
        chunks, vectors, None if origen == "usuario" else tarea, herramienta
    )
    drift_scores = drift.from_percentiles(refs)
    flagged = decision.decide(chunks, attack_scores, drift_scores, refs)
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


def describe() -> dict:
    """Qué guardián está corriendo, para anotar en los resultados (bench/)."""
    if os.environ.get("GUARD_MOCK") == "1":
        return {"modelo": "mock"}
    from guard import embedding, reference

    ref = reference.load(embedding.MODEL)
    return {
        "modelo": ref.model,
        "decision": "logística" if ref.method == "stack" else "regla",
        "umbrales": {
            k: v
            for k, v in ref.thresholds.items()
            if (k == "tau_stack") == (ref.method == "stack")
        },
        "datos": ref.data,
    }


def warmup() -> None:
    """Carga el modelo y la referencia (unos 15 s la primera vez) antes de medir latencias."""
    if os.environ.get("GUARD_MOCK") != "1":
        check("Warm up the guard before measuring.")


if os.environ.get("GUARD_MOCK") == "1":
    from guard.mock import check

__all__ = ["ORIGENES", "ToolCall", "check", "describe", "warmup"]
