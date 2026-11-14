"""Contrato 1 (docs/architecture.md): check(texto, tarea, origen) -> (permitido, info).

Versión 1 de docs/algorithm.md. El mock anterior sigue en guard/mock.py (GUARD_MOCK=1).
"""

from __future__ import annotations

import time
from functools import lru_cache

import numpy as np

from guard import config
from guard.chunks import Trozo, oraciones, trozos
from guard.embed import embed
from guard.model import cargar


@lru_cache(maxsize=256)
def _tarea_centrada(tarea: str, modelo: str) -> np.ndarray:
    return cargar(modelo).centrar(embed([tarea], modelo))[0]


def puntuar(texto: str, tarea: str | None = None, modelo: str = config.MODELO):
    """Spans de oraciones y, por trozo, (Trozo, attack_score, drift_score o None)."""
    p = cargar(modelo)
    spans = oraciones(texto)
    ts = trozos(texto, spans)
    if not ts:
        return spans, []
    v = p.centrar(embed([t.texto for t in ts], modelo))
    attack = p.attack_score(v)
    drift = p.drift_score(v, _tarea_centrada(tarea, modelo)) if tarea else [None] * len(ts)
    return spans, [(t, float(a), None if d is None else float(d)) for t, a, d in zip(ts, attack, drift)]


def _elegir(p, puntuados) -> list[tuple[Trozo, float, float | None]]:
    """Trozos marcados, de los más cortos a los más largos.

    Una ventana larga solo cuenta si ninguna de sus oraciones quedó ya marcada por
    una ventana más corta: así un ataque partido en dos oraciones se retira entero,
    pero una oración maliciosa no arrastra a sus vecinas legítimas.
    """
    marcadas: set[int] = set()
    elegidos = []
    for t, a, d in sorted(puntuados, key=lambda x: (x[0].ultima - x[0].primera, -x[1])):
        rango = set(range(t.primera, t.ultima + 1))
        if p.marcar(a, d) and not (rango & marcadas):
            marcadas |= rango
            elegidos.append((t, a, d))
    return elegidos


def _sanear(texto: str, spans: list[tuple[int, int]], marcadas: set[int]) -> str:
    """Reemplaza cada grupo de oraciones marcadas seguidas por un solo aviso."""
    partes, pos, i = [], 0, 0
    while i < len(spans):
        if i not in marcadas:
            i += 1
            continue
        j = i
        while j + 1 in marcadas:
            j += 1
        partes += [texto[pos : spans[i][0]], config.RETIRADO]
        pos, i = spans[j][1], j + 1
    return "".join(partes) + texto[pos:]


def check(texto: str, tarea: str | None = None, origen: str = "herramienta") -> tuple[bool, dict]:
    """Revisa un texto antes de que entre al contexto del agente.

    Devuelve (permitido, info). Ver los campos de info en docs/architecture.md.
    """
    if origen not in config.ORIGENES:
        raise ValueError(f"origen desconocido: {origen!r}; usar uno de {config.ORIGENES}")
    inicio = time.perf_counter()
    p = cargar()
    # El mensaje del usuario es la tarea: medir su desvío contra sí mismo no tiene sentido.
    spans, puntuados = puntuar(texto, None if origen == "usuario" else tarea)
    elegidos = _elegir(p, puntuados)
    marcadas = {i for t, _, _ in elegidos for i in range(t.primera, t.ultima + 1)}
    peor = max(puntuados, key=lambda x: x[1], default=None)
    info = {
        "texto_limpio": _sanear(texto, spans, marcadas) if marcadas else texto,
        "trozos_marcados": [
            {"texto": t.texto, "attack_score": round(a, 4), "drift_score": None if d is None else round(d, 4)}
            for t, a, d in sorted(elegidos, key=lambda x: x[0].primera)
        ],
        "attack_score": round(peor[1], 4) if peor else 0.0,
        "drift_score": (None if peor[2] is None else round(peor[2], 4)) if peor else None,
        "latencia_ms": (time.perf_counter() - inicio) * 1000,
        "origen": origen,
    }
    return not elegidos, info
