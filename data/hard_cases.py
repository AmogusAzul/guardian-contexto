"""Casos difíciles: dónde se equivoca el guardián actual (falsos positivos y negativos).

    python data/hard_cases.py                 # train + val (CSV y casos MCP) -> data/hard_cases.csv
    python data/hard_cases.py --splits val    # solo val

Corre `guard.check()` tal como está (no modifica guard/) y guarda cada error:

    FN          ataque que el guardián deja pasar
    FP          legítimo que el guardián marca (con guard-detect se descarta la salida entera)
    FN_trozo    ataque marcado, pero ninguno de los trozos marcados es la inyección: con
                guard-sanitize se retiraría texto legítimo y la inyección seguiría ahí

Orden: por tipo de error y, dentro de cada uno, de más a menos difícil (`rango`). En FN y FN_trozo, el attack_score más bajo de la inyección primero
(más lejos del umbral); en FP, el attack_score más alto primero. `margen` = distancia al umbral.

NO usa test.csv, mcp_test.jsonl ni paraphrase.csv: son el examen y se corren una sola vez con el
guardián congelado (CLAUDE.md, regla 6). Mirar sus errores para corregir datos o umbrales sería
ajustar con el examen.

Nota: el guardián se calibra con train, así que sus errores en train son pocos y suelen ser
ejemplos raros o mal etiquetados (revisarlos). Los de val son los que importan para mejorar.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from guard import ToolCall, check, chunking, embedding, reference  # noqa: E402
from guard import attack as gattack  # noqa: E402

DATA = ROOT / "data"
OUT = DATA / "hard_cases.csv"
FIELDS = ["rango", "error", "split", "archivo", "id", "label", "category", "source", "attack_score",
          "score_inyeccion", "umbral", "margen", "trozos_marcados", "injected_text", "prompt", "tool", "text"]


def _items(split: str):
    """(archivo, id, texto, fila, tarea, herramienta) de la CSV y de los casos MCP del split."""
    for i, r in enumerate(csv.DictReader(open(DATA / f"{split}.csv", encoding="utf-8"))):
        yield f"{split}.csv", f"{split}-csv-{i:04d}", r["text"], r, None, None
    for line in open(DATA / f"mcp_{split}.jsonl", encoding="utf-8"):
        c = json.loads(line)
        p = c["mcp_request"]["params"]
        text = "\n".join(x["text"] for x in c["mcp_response"]["result"]["content"] if x.get("type") == "text")
        tool = ToolCall(name=p["name"], description=c.get("tool_description") or "", arguments=p.get("arguments") or {})
        yield f"mcp_{split}.jsonl", c["id"], text, c, c.get("prompt"), tool


def _injection_score(text: str, injected: str) -> float | None:
    """attack_score más alto entre los trozos que son la inyección (guard/chunking.label)."""
    if not injected:
        return None
    _, chunks = chunking.chunk(text)
    idx = [i for i, c in enumerate(chunks) if chunking.label(c, injected) == "attack"]
    if not idx:
        return None
    scores = gattack.score(chunks, embedding.embed([c.text for c in chunks]))
    return max(scores[i] for i in idx)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--splits", nargs="+", default=["train", "val"], choices=["train", "val"])
    args = ap.parse_args()

    tau = reference.load(embedding.MODEL).thresholds["tau_high"]
    errors, totals = [], {}
    for split in args.splits:
        for archivo, cid, text, r, tarea, tool in _items(split):
            permitido, info = check(text, tarea=tarea, origen="herramienta", herramienta=tool)
            attack = r["label"] == "attack"
            t = totals.setdefault(archivo, {"ataques": 0, "legitimos": 0, "FN": 0, "FP": 0, "FN_trozo": 0})
            t["ataques" if attack else "legitimos"] += 1
            injected = r.get("injected_text") or ""
            marcados = info["trozos_marcados"]
            error = None
            if attack and permitido:
                error = "FN"
            elif not attack and not permitido:
                error = "FP"
            elif attack and injected:
                _, chunks = chunking.chunk(text)
                inj = {c.text for c in chunks if chunking.label(c, injected) == "attack"}
                if inj and not any(m["texto"] in inj for m in marcados):
                    error = "FN_trozo"
            if not error:
                continue
            t[error] += 1
            s_inj = _injection_score(text, injected) if attack else None
            score = s_inj if s_inj is not None else info["attack_score"]
            errors.append({
                "error": error, "split": split, "archivo": archivo, "id": cid, "label": r["label"],
                "category": r["category"], "source": r["source"],
                "attack_score": round(info["attack_score"], 4),
                "score_inyeccion": "" if s_inj is None else round(s_inj, 4),
                "umbral": round(tau, 4), "margen": round(score - tau, 4),
                "trozos_marcados": " || ".join(m["texto"] for m in marcados),
                "injected_text": injected, "prompt": tarea or "", "tool": tool.name if tool else "", "text": text,
                "_key": (score if error != "FP" else -score),
            })

    # Un mismo texto puede estar en el CSV y en un caso MCP: se deja una fila y se anotan los dos archivos.
    seen = {}
    for e in errors:
        k = (e["error"], e["text"])
        if k in seen:
            seen[k]["archivo"] += " + " + e["archivo"]
        else:
            seen[k] = e
    errors = list(seen.values())
    # Rango DENTRO de cada tipo de error. FN/FN_trozo: score de la inyección más bajo primero
    # (más lejos del umbral); FP: score más alto primero.
    order = {"FN": 0, "FN_trozo": 1, "FP": 2}
    errors.sort(key=lambda e: (order[e["error"]], e["_key"]))
    n = {}
    for e in errors:
        n[e["error"]] = n.get(e["error"], 0) + 1
        e["rango"] = n[e["error"]]
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(errors)

    print(f"umbral tau_high = {tau:.4f}")
    print(f"{'archivo':22} {'ataques':>8} {'legít.':>7} {'FN':>5} {'FN_trozo':>9} {'FP':>5}")
    for a, t in totals.items():
        print(f"{a:22} {t['ataques']:8} {t['legitimos']:7} {t['FN']:5} {t['FN_trozo']:9} {t['FP']:5}")
    print(f"{OUT.name}: {len(errors)} casos")


if __name__ == "__main__":
    main()
