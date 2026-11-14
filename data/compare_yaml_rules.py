"""Compara reglas de detección de YAML para guard/chunking._parse sobre el corpus.

    python data/compare_yaml_rules.py

Solo mide: reemplaza `_parse` EN MEMORIA dentro de este proceso; no modifica guard/.
Reglas (ver docs/yaml-findings.md):
    A  la actual: alguna línea con sangría o "- " después de la primera, y >= 2 elementos
    B  A + aceptar 1 clave raíz cuando hay sangría (sin claves repetidas en el primer nivel)
    C  B + aceptar YAML plano: >= 2 líneas, todas "clave: valor", clave sin espacios, sin repetidas
Necesita PyYAML.
"""

from __future__ import annotations

import collections
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data"))

import yaml  # noqa: E402

import guard.chunking as gc  # noqa: E402
from pipeline import YAML_SOURCES  # noqa: E402

ORIGINAL = gc._parse
_FLAT_LINE = re.compile(r"^[A-Za-z_][\w.-]*:( |$)")  # clave sin espacios


def _indented(t: str) -> bool:
    return any(line.startswith((" ", "\t", "- ")) for line in t.splitlines()[1:])


def _no_dup_keys(t: str) -> bool:
    """Claves del primer nivel repetidas: YAML pisaría líneas (un chat "Tom: …" dos veces)."""
    keys = [l.split(":", 1)[0] for l in t.splitlines() if l and not l.startswith((" ", "\t", "-"))]
    return len(keys) == len(set(keys))


def _rule(name: str):
    def _parse(s: str):
        fmt, tree, spans = ORIGINAL(s)
        if fmt != "text":
            return fmt, tree, spans
        t = s.strip()
        try:
            v = yaml.safe_load(t)
        except yaml.YAMLError:
            return fmt, tree, spans
        if not isinstance(v, (dict, list)):
            return fmt, tree, spans
        lines = t.splitlines()
        ok = name in ("B", "C") and _indented(t) and _no_dup_keys(t)
        ok |= name == "C" and len(lines) >= 2 and all(_FLAT_LINE.match(l) for l in lines) and _no_dup_keys(t)
        return ("yaml", v, {}) if ok else (fmt, tree, spans)

    return _parse


def _real_yaml(r: dict) -> bool:
    """Filas que Datos pasó a YAML (pipeline.yamlify): fuente estructurada, no JSON, YAML válido."""
    if r["source"] not in YAML_SOURCES:
        return False
    try:
        json.loads(r["text"])
        return False
    except ValueError:
        pass
    try:
        return isinstance(yaml.safe_load(r["text"]), (dict, list))
    except yaml.YAMLError:
        return False


def main() -> None:
    rows = [dict(r, split=s) for s in ("train", "val", "test")
            for r in csv.DictReader(open(ROOT / "data" / f"{s}.csv", encoding="utf-8"))]
    print(f"{'regla':34} {'YAML reconocido':>18} {'texto leído como YAML':>22} {'ataques YAML con trozo attack':>30} "
          f"{'claves visibles':>16} {'todos los ataques':>18}")
    for label, name in (("A  actual", "A"), ("B  + 1 clave raíz con sangría", "B"), ("C  B + YAML plano", "C")):
        gc._parse = ORIGINAL if name == "A" else _rule(name)
        st, wrong = collections.Counter(), collections.Counter()
        for r in rows:
            doc, chunks = gc.chunk(r["text"])
            real = _real_yaml(r)
            if real:
                st["yaml"] += 1
                st["yaml_ok"] += doc.format == "yaml"
            elif doc.format == "yaml":
                st["wrong"] += 1
                wrong[(r["source"], r["text"][:80])] += 1
            if r["label"] == "attack":
                hit = any(gc.label(c, r["injected_text"]) == "attack" for c in chunks)
                st["att"] += 1
                st["att_ok"] += hit
                if real:
                    st["att_y"] += 1
                    st["att_y_ok"] += hit
                if r["category"] == "key_injection":
                    st["key"] += 1
                    st["key_ok"] += any(gc.label(c, r["injected_text"]) == "attack" and c.kind == "path" for c in chunks)
        f = lambda a, b: f"{st[a]}/{st[b]} ({st[a] / max(1, st[b]):.0%})"
        print(f"{label:34} {f('yaml_ok', 'yaml'):>18} {st['wrong']:>22} {f('att_y_ok', 'att_y'):>30} "
              f"{f('key_ok', 'key'):>16} {st['att_ok']}/{st['att']} ({st['att_ok'] / st['att']:.1%})")
        for (src, t), n in wrong.most_common(3):
            print(f"      leído como YAML: {src}: {t!r}")
    gc._parse = ORIGINAL


if __name__ == "__main__":
    main()
