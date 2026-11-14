"""Muestra los trozos de casos de data/mcp_*.jsonl y cuáles son la inyección (guard/chunking.py).

    python -m guard.show_chunks data/mcp_train.jsonl --n 3
    python -m guard.show_chunks data/mcp_train.jsonl --id train-injecagent-0255

ATTACK = al menos 80 % del trozo es `injected_text` (será ataque al entrenar);
?? = toca la inyección sin serlo (se descarta); en blanco = legítimo.
"""

from __future__ import annotations

import argparse
import json

from guard.chunking import chunk, format_path, label


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Muestra los trozos de casos de data/mcp_*.jsonl"
    )
    ap.add_argument("jsonl")
    ap.add_argument("--id", help="un caso por su id")
    ap.add_argument(
        "--n", type=int, default=3, help="cuántos casos con inyección mostrar"
    )
    a = ap.parse_args()
    with open(a.jsonl, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    if a.id:
        rows = [r for r in rows if r["id"] == a.id]
    else:
        rows = [r for r in rows if r["injected_text"]][: a.n]
    marks = {"attack": "ATTACK", "benign": "      ", None: "  ??  "}
    for r in rows:
        doc, chunks = chunk(r["mcp_response"]["result"]["content"][0]["text"])
        print(f"\n== {r['id']} · {doc.format} · {len(chunks)} trozos")
        print(f"   inyección: {r['injected_text']!r}")
        for c in chunks:
            mark = marks[label(c, r["injected_text"])]
            print(f"{mark} {c.kind:<5} {format_path(c.path):<28} {c.text}")


if __name__ == "__main__":
    main()
