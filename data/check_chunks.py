"""Prueba los datos contra el troceo real del guardián (guard/chunking.py).

    python data/check_chunks.py                 # resumen por fuente
    python data/check_chunks.py --fallos 5      # y ejemplos de los casos que fallan

Para cada caso de data/mcp_*.jsonl y cada fila de data/*.csv con inyección, comprueba que el
troceo produzca al menos un trozo que `label()` marque como "attack" (que el guardián pueda
aprender y retirar la inyección), que sea del tipo esperado (`value` para inyecciones en
valores o texto, `path` para `key_injection`) y, si el caso trae `injected_path`, que esté en
esa ruta. En los legítimos cuenta los trozos (todos son "benign" por definición).
Necesita PyYAML (dependencia del paquete guard).
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from guard.chunking import chunk, format_path, label  # noqa: E402

DATA = ROOT / "data"


def evaluate(text: str, injected: str | None, category: str, injected_path: str | None) -> dict:
    doc, chunks = chunk(text)
    labels = [label(c, injected) for c in chunks]
    att = [c for c, l in zip(chunks, labels) if l == "attack"]
    want = "path" if category == "key_injection" else "value"
    # key_injection: el trozo de ruta del guardián en injected_path debe ser IGUAL a injected_text
    # (key_attacks.path_words replica sus reglas). None si no aplica; False si no hay trozo
    # (p. ej. la ruta queda con menos de MIN_WORDS palabras y el guardián la descarta).
    same = None
    if category == "key_injection" and injected_path:
        same = any(c.kind == "path" and format_path(c.path) == injected_path and c.text == injected
                   for c in chunks)
    return {
        "path_text_same": same,
        "format": doc.format,
        "n": len(chunks),
        "attack": bool(att),
        "kind_ok": any(c.kind == want for c in att),
        "path_ok": None if not injected_path else any(format_path(c.path) == injected_path for c in att),
        "ambiguous": sum(l is None for l in labels),
        "chunks": chunks,
        "labels": labels,
    }


def group(source: str) -> str:
    return "llmail" if source.startswith("llmail") else source.replace("synthetic_", "syn_")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fallos", type=int, default=0, help="cuántos ejemplos de fallos mostrar")
    a = ap.parse_args()

    for name, rows in (
        ("casos MCP (mcp_*.jsonl)", [
            dict(text=c["mcp_response"]["result"]["content"][0]["text"], injected=c["injected_text"],
                 category=c["category"], label=c["label"], source=c["source"], id=c["id"],
                 injected_path=c.get("injected_path"))
            for s in ("train", "val", "test") for c in map(json.loads, open(DATA / f"mcp_{s}.jsonl", encoding="utf-8"))]),
        ("corpus (train/val/test.csv)", [
            dict(text=r["text"], injected=r.get("injected_text") or None, category=r["category"], label=r["label"],
                 source=r["source"], id=f"{s}.csv", injected_path=None)
            for s in ("train", "val", "test") for r in csv.DictReader(open(DATA / f"{s}.csv", encoding="utf-8"))]),
    ):
        stats = collections.defaultdict(lambda: collections.Counter())
        fails = []
        for r in rows:
            e = evaluate(r["text"], r["injected"], r["category"], r["injected_path"])
            st = stats[group(r["source"])]
            st[f"fmt_{e['format']}"] += 1
            if r["label"] == "attack":
                st["att"] += 1
                st["att_ok"] += e["attack"]
                st["kind_ok"] += e["kind_ok"]
                st["amb"] += e["ambiguous"]
                st["chunks_att"] += e["n"]
                if e["path_ok"] is not None:
                    st["with_path"] += 1
                    st["path_ok"] += e["path_ok"]
                if e["path_text_same"] is not None:
                    st["keys"] += 1
                    st["keys_same"] += e["path_text_same"]
                if not (e["attack"] and e["kind_ok"]):
                    fails.append((r, e))
            else:
                st["ben"] += 1
                st["chunks_ben"] += e["n"]

        print(f"\n## {name}\n")
        print(f"{'fuente':26} {'ataques':>7} {'con trozo ATTACK':>17} {'tipo correcto':>14} {'ruta correcta':>14} "
              f"{'ambiguos/caso':>13} {'legítimos':>9} {'trozos/leg':>10}  formatos")
        tot = collections.Counter()
        for src, st in sorted(stats.items()):
            tot.update(st)
            fm = ", ".join(f"{k[4:]} {v}" for k, v in sorted(st.items()) if k.startswith("fmt_"))
            pct = lambda x, n: f"{x}/{n} ({x / n:.0%})" if n else "—"
            print(f"{src:26} {st['att']:7} {pct(st['att_ok'], st['att']):>17} {pct(st['kind_ok'], st['att']):>14} "
                  f"{pct(st['path_ok'], st['with_path']):>14} {st['amb'] / max(1, st['att']):13.1f} "
                  f"{st['ben']:9} {st['chunks_ben'] / max(1, st['ben']):10.1f}  {fm}")
        print(f"{'TOTAL':26} {tot['att']:7} {tot['att_ok']}/{tot['att']} ({tot['att_ok'] / max(1, tot['att']):.1%})"
              f"   tipo correcto {tot['kind_ok']}/{tot['att']}   ruta correcta {tot['path_ok']}/{tot['with_path']}")
        if tot["keys"]:
            print(f"key_injection: injected_text idéntico al trozo de ruta del guardián en "
                  f"{tot['keys_same']}/{tot['keys']}")

        for r, e in fails[: a.fallos]:
            print(f"\n-- FALLA {r['id']} [{r['source']} | {r['category']}] formato {e['format']}, {e['n']} trozos")
            print(f"   inyección: {r['injected'][:160]!r}")
            for c, l in list(zip(e["chunks"], e["labels"]))[:8]:
                mark = {"attack": "ATTACK", "benign": "      ", None: "  ??  "}[l]
                print(f"   {mark} {c.kind:<5} {format_path(c.path):<26} {c.text[:110]}")


if __name__ == "__main__":
    main()
