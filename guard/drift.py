"""Paso 4: drift_score de cada trozo (docs/algorithm.md, "4. drift_score").

1. Cosenos crudos con cada referencia que exista: pedido (el mensaje del usuario más parecido),
   llamada (nombre + descripción + argumentos) y vecinos (promedio de cosenos con cada uno).
2. Cada coseno pasa a percentil de los legítimos de su clase: todos dicen lo mismo.
3. m = el mejor encaje (basta una razón para estar ahí); 1 − m^k, con k referencias.
4. Como las referencias no son independientes, 1 − m^k no queda del todo parejo: se pasa por
   una última tabla por k (los legítimos de entrenamiento), y entonces sí queda parejo.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

import numpy as np

from guard import embedding, reference
from guard.chunking import Chunk, key_words
from guard.toolcall import ToolCall

MIN_PEERS = 3  # con menos vecinos, no hay referencia de vecinos
REFERENCES = ("request", "tool", "peers")
_TURN = re.compile(r"\s*\b(USER|ASSISTANT|SYSTEM)\s*:\s*")


def user_messages(task: str | None) -> list[str]:
    """Los mensajes del usuario: el texto entero, o sus turnos USER si es una conversación."""
    if not task:
        return []
    task = task.replace("<|endoftext|>", " ")
    parts = _TURN.split(task)
    msgs = [parts[0]] + [
        parts[i + 1] for i in range(1, len(parts) - 1, 2) if parts[i] == "USER"
    ]
    return [m.strip() for m in msgs if m.strip()]


def tool_text(tool: ToolCall | None) -> str | None:
    """Un solo texto con la llamada. Tiene que armarse igual al calibrar y en ejecución."""
    if tool is None:
        return None
    args = " ".join(str(v) for v in tool.arguments.values())
    return (
        " ".join(p for p in (key_words(tool.name), tool.description, args) if p).strip()
        or None
    )


def _overlap(a: Chunk, b: Chunk) -> bool:
    if a.path != b.path:
        return False
    if a.span is None or b.span is None:
        return True
    return a.span[0] < b.span[1] and b.span[0] < a.span[1]


def raw_cosines(
    chunks: Sequence[Chunk],
    vectors: np.ndarray,
    task: str | None,
    tool: ToolCall | None,
    model: str = embedding.MODEL,
) -> dict[str, list[float | None]]:
    """Coseno crudo de cada trozo con cada referencia (None si no existe). Lo usa también train."""
    n = len(chunks)
    out: dict[str, list[float | None]] = {r: [None] * n for r in REFERENCES}
    msgs = user_messages(task)
    if msgs and n:
        req = embedding.embed(msgs, model)
        out["request"] = [float(x) for x in (vectors @ req.T).max(axis=1)]
    text = tool_text(tool)
    if text and n:
        t = embedding.embed([text], model)[0]
        out["tool"] = [float(x) for x in vectors @ t]
    sims = vectors @ vectors.T if n else np.zeros((0, 0))
    for i, c in enumerate(chunks):
        peers = [
            j
            for j, d in enumerate(chunks)
            if j != i and d.kind == c.kind and d.group == c.group and not _overlap(c, d)
        ]
        if len(peers) >= MIN_PEERS:
            out["peers"][i] = float(sims[i, peers].mean())  # no depende de cuántos son
    return out


def combine(percentiles: Sequence[float | None]) -> tuple[float, int] | None:
    """(1 − m^k, k) con m = mejor percentil y k = cuántas referencias había."""
    ps = [p for p in percentiles if p is not None]
    if not ps:
        return None
    return 1.0 - max(ps) ** len(ps), len(ps)


Percentiles = dict[str, float | None]


def percentiles(
    chunks: Sequence[Chunk],
    vectors: np.ndarray,
    task: str | None,
    tool: ToolCall | None,
    model: str = embedding.MODEL,
) -> list[Percentiles]:
    """Por trozo, el percentil de su coseno con cada referencia (None si no existe)."""
    ref = reference.load(model)
    raws = raw_cosines(chunks, vectors, task, tool, model)
    return [
        {
            r: None
            if (x := raws[r][i]) is None
            else ref.percentile(f"drift-{r}", reference.chunk_class(c), x)
            for r in REFERENCES
        }
        for i, c in enumerate(chunks)
    ]


def score(
    chunks: Sequence[Chunk],
    vectors: np.ndarray,
    task: str | None,
    tool: ToolCall | None,
    model: str = embedding.MODEL,
) -> list[float | None]:
    """Un puntaje en [0, 1] por trozo; None si el trozo no tiene ninguna referencia."""
    return from_percentiles(percentiles(chunks, vectors, task, tool, model), model)


def from_percentiles(
    ps_list: Sequence[Percentiles], model: str = embedding.MODEL
) -> list[float | None]:
    """1 − m^k pasado por la tabla final de su k."""
    ref = reference.load(model)
    out: list[float | None] = []
    for ps in ps_list:
        comb = combine(list(ps.values()))
        if comb is None:
            out.append(None)
            continue
        value, k = comb
        final = ref.percentile(
            "drift", f"k{k}", value
        )  # None mientras se arma la referencia
        out.append(value if final is None else min(final, 1.0))
    return out
