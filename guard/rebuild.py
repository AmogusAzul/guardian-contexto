"""Paso 6: reconstruye la salida sin los trozos marcados (docs/algorithm.md, "6. Reconstrucción").

- value: el span marcado se reemplaza por el aviso; el resto del string se queda.
- path: se sube desde el valor mientras el padre tenga un solo hijo y se retira esa cadena.
- Mismo formato que la entrada: text y loose se editan en el string original; json, python y
  yaml se rearman y se vuelven a escribir. Un JSON que venía dentro de un string vuelve a ser string.
"""

from __future__ import annotations

import copy
import json
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

import yaml

from guard.chunking import Chunk, Document, Format, Path

PLACEHOLDER = "[contenido retirado por el guardián]"


def rebuild(doc: Document, flagged: Sequence[Chunk]) -> str:
    """El texto limpio. Sin nada marcado, devuelve el original tal cual."""
    if not flagged:
        return doc.original
    tree = copy.deepcopy(doc.tree)
    locations = [
        (c.kind, path, span)
        for c in flagged
        for path, span in ((c.path, c.span), *c.copies)
    ]

    # 1. Valores: todos los spans de un mismo string, de atrás hacia adelante.
    spans: dict[Path, list[tuple[int, int]]] = defaultdict(list)
    for kind, path, span in locations:
        if kind == "value" and span is not None:
            spans[path].append(span)
    for path, ss in spans.items():
        s = _get(tree, path)
        if isinstance(s, str):
            tree = _put(tree, path, _redact(s, ss))

    # 2. Rutas: la cadena de un solo hijo más alta, sin pasar por encima de una raíz.
    stops = {(), *doc.nested, *doc.roots}
    branches = {
        _branch(tree, path, stops) for kind, path, _ in locations if kind == "path"
    }
    removed: list[Path] = []
    for b in sorted(branches, key=len):
        if b and not any(b[: len(r)] == r for r in removed):
            _remove(tree, b)
            removed.append(b)

    # 3. Volver a escribir: primero las estructuras anidadas más profundas.
    for path in sorted(doc.nested, key=len, reverse=True):
        if path and not any(path[: len(r)] == r for r in removed):
            tree = _put(
                tree, path, _dump(doc.nested[path], _get(tree, path), doc, path)
            )
    if doc.format == "text":
        return tree
    return _dump(doc.format, tree, doc, ())


def _redact(s: str, spans: list[tuple[int, int]]) -> str:
    """Une los spans que se tocan o que solo separa espacio, y pone un aviso por grupo."""
    merged: list[list[int]] = []
    for a, b in sorted(spans):
        if merged and not s[merged[-1][1] : a].strip():
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    for a, b in reversed(merged):
        s = s[:a] + PLACEHOLDER + s[b:]
    return s


def _branch(tree: Any, path: Path, stops: set[Path]) -> Path:
    while (
        len(path) > 1 and path[:-1] not in stops and _size(_get(tree, path[:-1])) == 1
    ):
        path = path[:-1]
    return path


def _size(node: Any) -> int:
    return len(node) if isinstance(node, (dict, list)) else 0


def _remove(tree: Any, path: Path) -> None:
    """En un objeto se borra la clave (la clave puede ser el ataque); en una lista, aviso."""
    try:
        parent = _get(tree, path[:-1])
    except (KeyError, IndexError, TypeError):
        return
    if isinstance(parent, dict):
        parent.pop(path[-1], None)
    elif (
        isinstance(parent, list)
        and isinstance(path[-1], int)
        and path[-1] < len(parent)
    ):
        parent[path[-1]] = (
            PLACEHOLDER  # reemplazar, no borrar: no mueve los otros índices
        )


def _dump(fmt: Format, node: Any, doc: Document, path: Path) -> str:
    if fmt in ("json", "python"):
        return json.dumps(node, ensure_ascii=False)
    if fmt == "yaml":
        return yaml.safe_dump(node, allow_unicode=True, sort_keys=False)
    if fmt == "loose":  # editar el string original: cada valor en su lugar
        out = doc.sources.get(path, doc.original)
        for key, (a, b) in sorted(
            doc.loose_spans[path].items(), key=lambda kv: -kv[1][0]
        ):
            value = (
                node.get(key, PLACEHOLDER) if isinstance(node, dict) else PLACEHOLDER
            )
            out = out[:a] + str(value) + out[b:]
        return out
    return node if isinstance(node, str) else json.dumps(node, ensure_ascii=False)


def _get(tree: Any, path: Path) -> Any:
    for k in path:
        tree = tree[k]
    return tree


def _put(tree: Any, path: Path, value: Any) -> Any:
    if not path:
        return value
    _get(tree, path[:-1])[path[-1]] = value
    return tree
