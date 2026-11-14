"""Paso 1: parte una salida de herramienta en trozos de texto plano (docs/algorithm.md, "1. Trozos").

Autocontenido: biblioteca estándar y PyYAML. Nada de embeddings aquí.
Parsers en orden: json, python (ast.literal_eval), yaml (solo con sangría o "- "), loose, text.

Para ver los trozos de los casos de data/ y cuáles son la inyección: guard/show_chunks.py.
"""

from __future__ import annotations

import ast
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal

import yaml

Kind = Literal["value", "path"]
Format = Literal["json", "python", "yaml", "loose", "text"]
PathKey = str | int
Path = tuple[PathKey, ...]

WINDOWS = (1, 2, 3)  # oraciones por ventana, en trozos de valor
MIN_WORDS = 4  # trozos más cortos se descartan
SHORT_VALUE_WORDS = 6  # hasta aquí el valor también entra al trozo de ruta
MAX_CHUNKS = 500  # por encima: solo oraciones sueltas de valores
WHOLE_MAX_WORDS = 120  # valores y bloques enteros hasta aquí también son un trozo
COVERAGE = 0.8  # un trozo "es la inyección" si al menos este tanto de su texto lo es


@dataclass(frozen=True)
class Chunk:
    text: str  # lo que se embebe: limpio, sin sintaxis JSON
    kind: Kind
    path: Path  # ubicación del string (value) o del valor (path) en Document.tree
    span: tuple[int, int] | None = (
        None  # (inicio, fin) dentro de ese string; solo value
    )
    group: str = (
        ""  # vecinos: ruta sin índices ("$.emails[*].body") o bloques de un texto
    )
    size: int = 0  # oraciones en la ventana (0 = valor o bloque entero, o ruta)


@dataclass
class Document:
    """La salida ya parseada: lo necesario para reconstruirla en el mismo formato."""

    original: str
    format: Format
    tree: Any  # dict/list parseado, o el string si es texto
    # strings que traían una estructura (JSON en un string, bloque text de MCP): su formato
    nested: dict[Path, Format] = field(default_factory=dict)
    # estructuras "loose": por cada una, dónde está cada valor dentro de su string original
    loose_spans: dict[Path, dict[str, tuple[int, int]]] = field(default_factory=dict)
    # el string original de cada estructura anidada (para reemplazar sin reescribir)
    sources: dict[Path, str] = field(default_factory=dict)
    roots: set[Path] = field(default_factory=set)  # bloques de un resultado MCP


# ---------------------------------------------------------------- parsear

_LOOSE_KEY = re.compile(r"[{,]\s*['\"]([^'\"\n]{1,60})['\"]\s*:\s*")
_LOOSE_TRIM_START = re.compile(r"[\s{\['\"]+")
_LOOSE_TRIM_END = re.compile(r"[\s}\]'\",]+$")


def _parse(s: str) -> tuple[Format, Any, dict[str, tuple[int, int]]]:
    """(formato, árbol, posiciones de los valores si es loose)."""
    t = s.strip()
    try:
        v = json.loads(t)
        if isinstance(v, (dict, list)):
            return "json", v, {}
    except ValueError:
        pass
    if t[:1] in "{[":
        try:
            v = ast.literal_eval(t)
            if isinstance(v, (dict, list)):
                return "python", v, {}
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            pass
    # Solo YAML de verdad: un chat "Nombre: mensaje" también parsea como YAML y las
    # claves repetidas se pisan (se pierden líneas, y con ellas un ataque).
    if any(line.startswith((" ", "\t", "- ")) for line in t.splitlines()[1:]):
        try:
            v = yaml.safe_load(t)
            if isinstance(v, (dict, list)) and len(v) >= 2:
                return "yaml", v, {}
        except yaml.YAMLError:
            pass
    if t[:1] in "{[":
        tree, spans = _loose(s)
        if tree:
            return "loose", tree, spans
    return "text", s, {}


def _loose(s: str) -> tuple[dict[str, str], dict[str, tuple[int, int]]]:
    """Estructura que no parsea (la inyección rompió las comillas): cortar en 'clave':."""
    ms = list(_LOOSE_KEY.finditer(s))
    if not ms:
        return {}, {}
    tree: dict[str, str] = {}
    spans: dict[str, tuple[int, int]] = {}
    for m, nxt in zip(ms, [*ms[1:], None], strict=True):
        start, end = m.end(), nxt.start() if nxt else len(s)
        lead = _LOOSE_TRIM_START.match(s, start, end)
        start = lead.end() if lead else start
        tail = _LOOSE_TRIM_END.search(s, start, end)
        end = tail.start() if tail else end
        if end <= start:
            continue
        key = m.group(1) if m.group(1) not in tree else f"{m.group(1)}_{len(tree)}"
        tree[key] = s[start:end]
        spans[key] = (start, end)
    return tree, spans


# ---------------------------------------------------------------- texto

_ZERO_WIDTH = re.compile("[\u200b-\u200f\u2060\ufeff]")
_BLOCK = re.compile(r"\n[ \t]*-{3,}[ \t]*\n|\n[ \t]*\n")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(<#\[])")
_HTML_TAG = re.compile(r"</?[a-zA-Z][^<>]{0,200}>")  # no toca <|system|>
_ABBREV = re.compile(
    r"\b(?:Dr|Mr|Mrs|Ms|Prof|St|Jr|Sr|Inc|Ltd|Co|vs|etc|e\.g|i\.e|No|Fig)\.$"
)
_ID = re.compile(r"^[0-9a-f-]{6,}$|^\d{4}-\d{2}-\d{2}|^[\d.,:%/ $€+-]+$", re.IGNORECASE)


def clean(t: str) -> str:
    """Lo que ve el modelo: NFC, sin ancho cero ni etiquetas HTML (su texto se queda), espacios colapsados."""
    t = unicodedata.normalize("NFC", t)
    t = (
        _ZERO_WIDTH.sub("", t)
        .replace("<!--", " ")
        .replace("-->", " ")
        .replace("[//]: #", " ")
    )
    t = _HTML_TAG.sub(
        " ", t
    )  # <span style="display:none">…</span>: queda el texto de adentro
    return re.sub(r"\s+", " ", t).strip()


def _key_words(k: PathKey) -> str:
    k = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(k))
    k = re.sub(
        r"([A-Z]+)([A-Z][a-z])", r"\1 \2", k
    )  # "IMPORTANTAssistant" -> "IMPORTANT Assistant"
    return re.sub(r"[\W_]+", " ", k).strip().lower()


def _trim(s: str, a: int, b: int) -> tuple[int, int]:
    while a < b and s[a].isspace():
        a += 1
    while b > a and s[b - 1].isspace():
        b -= 1
    return a, b


def _blocks(s: str) -> list[list[tuple[int, int]]]:
    """Bloques (--- o línea en blanco) -> líneas -> oraciones, como posiciones en s."""
    bounds, pos = [], 0
    for m in _BLOCK.finditer(s):
        bounds.append((pos, m.start()))
        pos = m.end()
    bounds.append((pos, len(s)))
    blocks = []
    for bs, be in bounds:
        sents = []
        ls = bs
        while ls <= be:
            nl = s.find("\n", ls, be)
            le = be if nl == -1 else nl
            pos = ls
            for m in _SENTENCE.finditer(s, ls, le):
                if _ABBREV.search(
                    s, pos, m.start()
                ):  # "Dr. Smith" no es fin de oración
                    continue
                sents.append(_trim(s, pos, m.start()))
                pos = m.end()
            sents.append(_trim(s, pos, le))
            ls = le + 1
        blocks.append([(a, b) for a, b in sents if b > a])
    return [b for b in blocks if b]


def _value_chunks(s: str, path: Path, group: str, out: list[Chunk]) -> None:
    """Ventanas de 1 a 3 oraciones dentro de cada bloque, y el bloque entero si es corto."""
    blocks = _blocks(s)
    if len(blocks) > 1:
        group = f"{group}#blocks"  # los bloques de un texto son vecinos entre sí
    for sents in blocks:
        n = len(sents)
        for k in WINDOWS:
            for i in range(n - k + 1):
                span = (sents[i][0], sents[i + k - 1][1])
                out.append(
                    Chunk(clean(s[span[0] : span[1]]), "value", path, span, group, k)
                )
        whole = (sents[0][0], sents[-1][1])
        text = clean(s[whole[0] : whole[1]])
        if n > max(WINDOWS) and len(text.split()) <= WHOLE_MAX_WORDS:
            out.append(Chunk(text, "value", path, whole, group, 0))


# ---------------------------------------------------------------- recorrer


def format_path(path: Path) -> str:
    """("emails", 1, "body") -> "$.emails[1].body"."""
    return "$" + "".join(f"[{k}]" if isinstance(k, int) else f".{k}" for k in path)


def _group(path: Path) -> str:
    return "$" + "".join("[*]" if isinstance(k, int) else f".{k}" for k in path)


def _walk(
    node: Any, path: Path, keys: list[str], doc: Document, out: list[Chunk]
) -> None:
    if isinstance(node, str) and (node.strip()[:1] in "{[" or path in doc.roots):
        fmt, tree, spans = _parse(node)
        if fmt != "text":
            _set(doc, path, tree, fmt, node, spans)
            node = tree
    if isinstance(node, dict):
        for k, v in node.items():
            _walk(v, (*path, k), [*keys, _key_words(k)], doc, out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk(v, (*path, i), keys, doc, out)
    else:
        v = "" if node is None or isinstance(node, bool) else str(node)
        is_text = isinstance(node, str) and bool(v.strip()) and not _ID.match(v.strip())
        if is_text:
            _value_chunks(v, path, _group(path), out)
        short = v if is_text and len(v.split()) <= SHORT_VALUE_WORDS else ""
        out.append(
            Chunk(clean(" ".join([*keys, short])), "path", path, None, _group(path))
        )


def _set(
    doc: Document, path: Path, tree: Any, fmt: Format, source: str, spans: dict
) -> None:
    """Reemplaza en doc.tree el string de `path` por su estructura, y anota cómo volver."""
    if not path:
        doc.tree = tree
    else:
        parent = doc.tree
        for k in path[:-1]:
            parent = parent[k]
        parent[path[-1]] = tree
    doc.nested[path] = fmt
    doc.sources[path] = source
    if fmt == "loose":
        doc.loose_spans[path] = spans


def _mcp_roots(tree: Any) -> list[Path] | None:
    """Rutas de lo que trae un resultado MCP (bloques text, resource.text, structuredContent)."""
    base: Path = ()
    if isinstance(tree, dict) and isinstance(tree.get("result"), dict):
        tree, base = tree["result"], ("result",)
    if not (isinstance(tree, dict) and isinstance(tree.get("content"), list)):
        return None
    if not all(isinstance(c, dict) and "type" in c for c in tree["content"]):
        return None
    roots: list[Path] = []
    for i, c in enumerate(tree["content"]):
        if c["type"] == "text" and isinstance(c.get("text"), str):
            roots.append((*base, "content", i, "text"))
        elif c["type"] == "resource" and isinstance(
            c.get("resource", {}).get("text"), str
        ):
            roots.append((*base, "content", i, "resource", "text"))
    if "structuredContent" in tree:
        roots.append((*base, "structuredContent"))
    return roots


def chunk(text: str) -> tuple[Document, list[Chunk]]:
    """Parsea, recorre la estructura (o los bloques del texto) y devuelve sus trozos."""
    fmt, tree, spans = _parse(text)
    doc = Document(text, fmt, tree)
    if fmt == "loose":
        doc.loose_spans[()] = spans
    raw: list[Chunk] = []
    if fmt == "text":
        _value_chunks(text, (), "$", raw)
    else:
        roots = _mcp_roots(tree)
        doc.roots = set(roots or [])
        for root in roots if roots is not None else [()]:
            node = doc.tree
            for k in root:
                node = node[k]
            _walk(
                node, root, [], doc, raw
            )  # las claves del sobre MCP no entran al texto

    seen: set[tuple[str, str]] = set()
    chunks = []
    for c in raw:
        if len(c.text.split()) >= MIN_WORDS and (c.kind, c.text) not in seen:
            seen.add((c.kind, c.text))
            chunks.append(c)
    if len(chunks) > MAX_CHUNKS:  # nunca se salta una parte: se quitan ventanas y rutas
        chunks = [c for c in chunks if c.kind == "value" and c.size == 1]
    return doc, chunks


# ---------------------------------------------------------------- etiquetas


def label(c: Chunk, injected_text: str | None) -> str | None:
    """Etiqueta de entrenamiento: "attack", "benign" o None (ambiguo, se descarta).

    attack: al menos COVERAGE del trozo es la inyección. benign: no la toca.
    """
    if not injected_text:
        return "benign"
    inj, text = (
        clean(injected_text).lower(),
        c.text.lower(),
    )  # las rutas van en minúsculas
    if text in inj or (inj in text and len(inj) >= COVERAGE * len(text)):
        return "attack"
    if inj in text or _overlap(text, inj):
        return None
    return "benign"


def _overlap(a: str, b: str, n: int = 6) -> bool:
    """¿Comparten alguna secuencia de n palabras?"""
    wa, wb = a.split(), b.split()
    grams = {tuple(wb[i : i + n]) for i in range(len(wb) - n + 1)}
    return any(tuple(wa[i : i + n]) in grams for i in range(len(wa) - n + 1))
