"""Canalización de calidad del corpus (Contrato 3). Se ejecuta con `python data/build.py`.

1. Reúne las fuentes: sintéticos (build.py) + LLMail-Inject + InjecAgent + NotInject (sources.py).
2. Normaliza cada texto (Unicode NFC, saltos de línea, caracteres de control).
3. Reevalúa cada fila con los criterios de calidad; las que fallan van a data/rejected.csv con su motivo.
4. Quita duplicados exactos, textos con etiquetas en conflicto y casi-duplicados (también entre splits).
5. Equilibra cada split: 50/50 ataque/legítimo, ninguna fuente > 45 % del split, y dentro de cada
   fuente con ambas etiquetas ninguna etiqueta > 75 % (para que la fuente no delate la etiqueta).
6. Escribe train/val/test.csv, rejected.csv y QUALITY.md (composición, atajos y fugas medidos).
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import random
import re
import statistics
import sys
import unicodedata
from pathlib import Path

import sources
from build import AGENTDOJO_SIGNATURES, EVIL, SEED, gen_synthetic, make_json_attack

DATA = Path(__file__).resolve().parent
SPLITS = ("train", "val", "test")
SPLIT_PRIORITY = {"test": 0, "val": 1, "train": 2}

MIN_WORDS, MIN_CHARS, MAX_CHARS = 4, 20, 2500
NEAR_DUP_JACCARD = 0.85
TARGET_ATTACK_SHARE = 0.5
MAX_SOURCE_SHARE = 0.45
MAX_LABEL_SHARE_IN_SOURCE = 0.75

# Patrones de inyección explícita: un texto "legítimo" que los tenga es una etiqueta sospechosa.
EXPLICIT_INJECTION = re.compile(
    r"ignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|prompts?|messages?)"
    r"|disregard (all |the )?(previous|prior|above) (instructions|guidance)"
    r"|(new|updated) instructions? for (the )?(ai|assistant|model|agent)"
    r"|you are now in [a-z ]*mode|<\|?system\|?>|\bsystem prompt\b|do not (tell|mention|inform) the user",
    re.IGNORECASE,
)
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD = re.compile(r"\b(?:\d{4}[ -]?){3}\d{3,4}\b")
MOJIBAKE = re.compile(r"Ã[\x80-\xbf]|â€|Â\s")


def _luhn(digits: str) -> bool:
    d = [int(c) for c in digits][::-1]
    return sum(x if i % 2 == 0 else (x * 2 - 9 if x * 2 > 9 else x * 2) for i, x in enumerate(d)) % 10 == 0


# --------------------------------------------------------------------------------------
# 2-3. Normalización y criterios por fila
# --------------------------------------------------------------------------------------

def normalize(text: str) -> str:
    t = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    # Fuera caracteres de control (Cc) salvo \n y \t. Los de formato (Cf, p. ej. zero-width) se
    # conservan: son parte de algunos ataques ofuscados.
    t = "".join(c for c in t if c in "\n\t" or unicodedata.category(c) != "Cc")
    t = "\n".join(line.rstrip() for line in t.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", t).strip()


_EN = set("the and is are you what how of to in for please my your this that with on it be will was have".split())
_OTHER = set(
    "und ich nicht der die das ist sie mit bitte auf wird auch eine "           # de
    "el los las que por para una con del está pero como más "                 # es
    "le les des est pour avec qui dans pas vous nous sur "                     # fr
    "não uma com para os ao mas "                                              # pt
    "il che non della sono per".split())                                       # it


def is_other_language(text: str) -> bool:
    """Otro idioma con alfabeto latino: más palabras funcionales de de/es/fr/pt/it que de inglés.
    Un JSON o un texto con pocas palabras no se marca (no hay evidencia)."""
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    other = sum(w in _OTHER for w in words)
    return other >= 3 and other > sum(w in _EN for w in words)


def _latin_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum("LATIN" in unicodedata.name(c, "") for c in letters) / len(letters)


def span_found(row: dict) -> bool:
    """¿El fragmento malicioso (`injected_text`) aparece en `text`? Tal cual, o escapado como
    cadena JSON cuando va dentro de un campo (InjecAgent, Glaive, api_json). Los ataques en
    claves (`key_injection`) se excluyen: su `injected_text` es la ruta en palabras (path_words)."""
    inj, t = row.get("injected_text") or "", row["text"]
    return bool(inj) and (inj in t or json.dumps(inj, ensure_ascii=False)[1:-1] in t)


def quality_issues(row: dict) -> list[str]:
    t = row["text"]
    issues = []
    n_words = len(re.findall(r"\w+", t))
    if n_words < MIN_WORDS or len(t) < MIN_CHARS:
        issues.append("too_short")
    if len(t) > MAX_CHARS:
        issues.append("too_long")
    if "�" in t or MOJIBAKE.search(t):
        issues.append("encoding_garbage")
    if _latin_ratio(t) < 0.8 or is_other_language(t):
        issues.append("not_english")
    if SSN.search(t) or any(_luhn(re.sub(r"\D", "", m.group())) for m in CARD.finditer(t)):
        issues.append("pii_like")
    if any(sig.lower() in t.lower() for sig in AGENTDOJO_SIGNATURES):
        issues.append("agentdojo_leak")
    if row["label"] == "benign" and EXPLICIT_INJECTION.search(t):
        issues.append("benign_with_injection_pattern")
    if row["label"] == "attack" and row.get("category") != "key_injection" and not span_found(row):
        issues.append("injected_text_not_found")
    if row["label"] not in ("attack", "benign") or not re.fullmatch(r"[a-z0-9]+(_[a-z0-9]+)*", row["category"]):
        issues.append("bad_label_or_category")
    return issues


# --------------------------------------------------------------------------------------
# 4. Duplicados
# --------------------------------------------------------------------------------------

def _key(t: str) -> str:
    return re.sub(r"\s+", " ", t.lower()).strip()


def _words(t: str) -> frozenset:
    return frozenset(re.findall(r"[a-z]+", re.sub(r"\d", "0", t.lower())))


def dedup(rows: list[dict], rejected: list[dict]) -> list[dict]:
    # Etiquetas en conflicto: el mismo texto como ataque y como legítimo -> fuera ambos.
    labels = collections.defaultdict(set)
    for r in rows:
        labels[_key(r["text"])].add(r["label"])
    out = []
    for r in rows:
        if len(labels[_key(r["text"])]) > 1:
            rejected.append(dict(r, reason="conflicting_labels"))
        else:
            out.append(r)
    # Exactos y casi-duplicados. Se conserva primero test, luego val: si un texto de train se
    # parece a uno de test, se va el de train (protege la evaluación).
    out.sort(key=lambda r: (SPLIT_PRIORITY[r["split"]], r["source"]))
    kept, seen, kept_words = [], set(), []
    for r in out:
        k = _key(r["text"])
        if k in seen:
            rejected.append(dict(r, reason="exact_duplicate"))
            continue
        w = _words(r["text"])
        if any(len(w & o) / max(1, len(w | o)) >= NEAR_DUP_JACCARD for o in kept_words):
            rejected.append(dict(r, reason="near_duplicate"))
            continue
        seen.add(k)
        kept.append(r)
        kept_words.append(w)
    return kept


# --------------------------------------------------------------------------------------
# 5. Equilibrio
# --------------------------------------------------------------------------------------

def _drop(pool: list[dict], n: int, rng: random.Random, reason: str, rejected: list[dict]) -> list[dict]:
    """Quita n filas del pool empezando por la categoría más abundante (conserva diversidad)."""
    pool = list(pool)
    rng.shuffle(pool)
    for _ in range(max(0, n)):
        if not pool:
            break
        top = collections.Counter(r["category"] for r in pool).most_common(1)[0][0]
        idx = next(i for i, r in enumerate(pool) if r["category"] == top)
        rejected.append(dict(pool.pop(idx), reason=reason))
    return pool


def balance(rows: list[dict], rng: random.Random, rejected: list[dict]) -> list[dict]:
    out = []
    for split in SPLITS:
        part = [r for r in rows if r["split"] == split]

        # (a) dentro de cada fuente con ambas etiquetas, ninguna etiqueta > 75 %
        by_src = collections.defaultdict(list)
        for r in part:
            by_src[r["source"]].append(r)
        part = []
        for src, rs in by_src.items():
            att = [r for r in rs if r["label"] == "attack"]
            ben = [r for r in rs if r["label"] == "benign"]
            if att and ben:
                cap = lambda other: int(len(other) * MAX_LABEL_SHARE_IN_SOURCE / (1 - MAX_LABEL_SHARE_IN_SOURCE))
                att = _drop(att, len(att) - cap(ben), rng, "balance_label_within_source", rejected)
                ben = _drop(ben, len(ben) - cap(att), rng, "balance_label_within_source", rejected)
            part += att + ben

        for _ in range(5):  # (b) y (c) interactúan: iterar hasta estabilizar
            # (b) ninguna fuente > 45 % del split
            total = len(part)
            counts = collections.Counter(r["source"] for r in part)
            for src, c in counts.items():
                if c > MAX_SOURCE_SHARE * total and len(counts) > 1:
                    others = total - c
                    allowed = int(MAX_SOURCE_SHARE / (1 - MAX_SOURCE_SHARE) * others)
                    rs = [r for r in part if r["source"] == src]
                    part = [r for r in part if r["source"] != src]
                    for lab in ("attack", "benign"):  # recorte proporcional por etiqueta
                        lr = [r for r in rs if r["label"] == lab]
                        part += _drop(lr, len(lr) - round(allowed * len(lr) / c), rng, "balance_source_cap", rejected)
            # (c) 50/50 ataque/legítimo: recortar la etiqueta mayoritaria, desde su fuente más grande
            att = [r for r in part if r["label"] == "attack"]
            ben = [r for r in part if r["label"] == "benign"]
            major, minor = (att, ben) if len(att) > len(ben) else (ben, att)
            excess = len(major) - len(minor)
            if excess <= 0.02 * len(part):
                break
            # Recorte emparejado por longitud: se quita de la franja de largo donde la etiqueta
            # mayoritaria está más sobrerrepresentada (así la longitud deja de delatar la etiqueta),
            # dentro de ella de la fuente más grande y de su categoría más abundante.
            lengths = sorted(len(r["text"]) for r in part)
            edges = [lengths[int(len(lengths) * q / 8)] for q in range(1, 8)]
            bin_of = lambda r: sum(len(r["text"]) > e for e in edges)
            minor_bins = collections.Counter(bin_of(r) for r in minor)
            while excess > 0:
                major_bins = collections.Counter(bin_of(r) for r in major)
                b = max(major_bins, key=lambda k: major_bins[k] / len(major) - minor_bins.get(k, 0) / max(1, len(minor)))
                cand = [r for r in major if bin_of(r) == b]
                src = collections.Counter(r["source"] for r in cand).most_common(1)[0][0]
                cand = [r for r in cand if r["source"] == src]
                cat = collections.Counter(r["category"] for r in cand).most_common(1)[0][0]
                victim = rng.choice([r for r in cand if r["category"] == cat])
                major = [r for r in major if r is not victim]
                rejected.append(dict(victim, reason="balance_attack_benign"))
                excess -= 1
            part = major + minor
        out += part
    return out


# --------------------------------------------------------------------------------------
# 6. Reporte
# --------------------------------------------------------------------------------------

def _auc(pos: list[float], neg: list[float]) -> float:
    if not pos or not neg:
        return float("nan")
    ranked = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    # AUC por rangos (Mann-Whitney), con empates promediados
    rank_sum, i = 0.0, 0
    while i < len(ranked):
        j = i
        while j < len(ranked) and ranked[j][0] == ranked[i][0]:
            j += 1
        avg = (i + j + 1) / 2
        rank_sum += avg * sum(1 for k in range(i, j) if ranked[k][1] == 1)
        i = j
    return (rank_sum - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def report(final: list[dict], rejected: list[dict], n_input: int) -> str:
    L = []
    L.append("# Calidad del corpus\n")
    L.append("Generado por `python data/build.py`. No editar a mano.\n")
    L.append(f"Filas candidatas: {n_input}. Aceptadas: {len(final)}. Descartadas: {len(rejected)} "
             f"(detalle fila por fila en `rejected.csv`).\n")

    L.append("## Composición final\n")
    L.append("| Split | Filas | Ataques | Legítimos | % ataque | Hard negatives (% de legítimos) |")
    L.append("|---|---|---|---|---|---|")
    for s in SPLITS:
        p = [r for r in final if r["split"] == s]
        a = sum(r["label"] == "attack" for r in p)
        b = len(p) - a
        h = sum(r["category"] == "hard_negative" for r in p)
        L.append(f"| {s} | {len(p)} | {a} | {b} | {a / max(1, len(p)):.0%} | {h} ({h / max(1, b):.0%}) |")

    L.append("\n### Por fuente\n")
    L.append("| Split | Fuente | Ataques | Legítimos | % del split |")
    L.append("|---|---|---|---|---|")
    for s in SPLITS:
        p = [r for r in final if r["split"] == s]
        for src in sorted({r["source"] for r in p}):
            rs = [r for r in p if r["source"] == src]
            a = sum(r["label"] == "attack" for r in rs)
            L.append(f"| {s} | {src} | {a} | {len(rs) - a} | {len(rs) / len(p):.0%} |")

    L.append("\n### Categorías\n")
    cats = sorted({r["category"] for r in final})
    L.append("| Categoría | " + " | ".join(SPLITS) + " |")
    L.append("|---|" + "---|" * len(SPLITS))
    for c in cats:
        L.append(f"| {c} | " + " | ".join(str(sum(1 for r in final if r['split'] == s and r['category'] == c)) for s in SPLITS) + " |")

    L.append("\n## Descartes por criterio\n")
    reasons = sorted({r["reason"] for r in rejected})
    srcs = sorted({r["source"] for r in rejected})
    L.append("| Motivo | " + " | ".join(srcs) + " |")
    L.append("|---|" + "---|" * len(srcs))
    for rs in reasons:
        L.append(f"| {rs} | " + " | ".join(str(sum(1 for r in rejected if r['reason'] == rs and r['source'] == s)) for s in srcs) + " |")

    L.append("\n## Atajos medidos (0,5 = la señal no ayuda a separar)\n")
    L.append("Un detector podría aprender estas señales en vez de la intención. Se miden para vigilarlas.\n")
    L.append("La AUC *dentro de fuente* (promedio ponderado entre fuentes con ambas etiquetas) es la que "
             "importa para el entrenamiento; la del split completo mezcla estilos de fuentes distintas.\n")
    L.append("| Split | AUC longitud (split) | AUC longitud (dentro de fuente) | Ataques con URL/correo | Legítimos con URL/correo | Ataques con 'assistant'/'AI' | Legítimos con 'assistant'/'AI' |")
    L.append("|---|---|---|---|---|---|---|")
    link = re.compile(r"https?://|@[\w-]+\.")
    addr = re.compile(r"\b(assistant|ai|model|agent|llm)\b", re.IGNORECASE)
    for s in SPLITS:
        p = [r for r in final if r["split"] == s]
        A = [r for r in p if r["label"] == "attack"]
        B = [r for r in p if r["label"] == "benign"]
        frac = lambda rs, rx: sum(bool(rx.search(r["text"])) for r in rs) / max(1, len(rs))
        within, weight = 0.0, 0
        for src in {r["source"] for r in p}:
            a = [len(r["text"]) for r in A if r["source"] == src]
            b = [len(r["text"]) for r in B if r["source"] == src]
            if a and b:
                within += _auc(a, b) * (len(a) + len(b))
                weight += len(a) + len(b)
        L.append(f"| {s} | {_auc([len(r['text']) for r in A], [len(r['text']) for r in B]):.2f} | "
                 f"{within / max(1, weight):.2f} | "
                 f"{frac(A, link):.0%} | {frac(B, link):.0%} | {frac(A, addr):.0%} | {frac(B, addr):.0%} |")

    L.append("\n## Verificaciones de fuga\n")
    keys = {s: {_key(r["text"]) for r in final if r["split"] == s} for s in SPLITS}
    cross = sum(len(keys[a] & keys[b]) for i, a in enumerate(SPLITS) for b in SPLITS[i + 1:])
    L.append(f"- Textos idénticos entre splits: **{cross}**.")
    srcs_by_split = {s: {r['source'] for r in final if r['split'] == s} for s in SPLITS}
    shared = {src for i, a in enumerate(SPLITS) for b in SPLITS[i + 1:] for src in srcs_by_split[a] & srcs_by_split[b]}
    L.append(f"- Fuentes presentes en más de un split: {', '.join(sorted(shared)) or 'ninguna'} "
             "(separadas por tema, herramienta, caso de ataque o subconjunto; ver README).")
    leaks = sum(any(sig.lower() in r["text"].lower() for sig in AGENTDOJO_SIGNATURES) for r in final)
    L.append(f"- Filas con firmas de AgentDojo: **{leaks}**.")
    evil_cross = 0
    for s in SPLITS:
        others = {v for o in SPLITS if o != s for vs in EVIL[o].values() for v in vs}
        evil_cross += sum(any(v in r["text"] for v in others) for r in final if r["split"] == s)
    L.append(f"- Filas con datos de atacante de otro split: **{evil_cross}**.")

    med = {s: statistics.median(len(r["text"]) for r in final if r["split"] == s) for s in SPLITS}
    L.append("\n## Longitud mediana (caracteres)\n")
    L.append(", ".join(f"{s}: {m:.0f}" for s, m in med.items()) + "\n")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="solo sintéticos y lo que ya esté en data/raw y data/pools")
    args = ap.parse_args()

    rng = random.Random(SEED)
    evil_emails = {s: EVIL[s]["evil_email"] for s in SPLITS}
    rows = gen_synthetic(rng, reps=1, composed=40, attacks_per_family=42)
    loaders = [("LLMail-Inject ataques", lambda: sources.llmail_attacks(evil_emails)),
               ("LLMail-Inject legítimos", sources.llmail_benign),
               ("InjecAgent", lambda: sources.injecagent(evil_emails)),
               ("Glaive (respuestas de funciones)", lambda: sources.glaive(make_json_attack)),
               ("NotInject", sources.notinject)]
    for name, load in loaders:
        try:
            got = load()
            rows += got
            print(f"{name}: {len(got)} filas")
        except Exception as e:  # sin red: seguir con lo que haya
            if not args.offline:
                print(f"AVISO: {name} no disponible ({e})", file=sys.stderr)

    n_input = len(rows)
    rejected: list[dict] = []
    clean = []
    for r in rows:
        r = dict(r, text=normalize(r["text"]))
        if r.get("injected_text"):
            r["injected_text"] = normalize(r["injected_text"])
        issues = quality_issues(r)
        if issues:
            rejected.append(dict(r, reason="+".join(issues)))
        else:
            clean.append(r)
    clean = dedup(clean, rejected)

    # Ataques en las CLAVES del JSON (docs/data-key-attacks.md), sobre salidas JSON ya aceptadas.
    # Van después de la deduplicación a propósito: cada uno es su portador + una clave (pares mínimos).
    import key_attacks
    carriers = [r for r in clean if r["source"] in ("glaive_function_responses", "injecagent")]
    for r in key_attacks.generate(carriers):
        r = dict(r, text=normalize(r["text"]))
        issues = quality_issues(r)
        (rejected.append(dict(r, reason="+".join(issues))) if issues else clean.append(r))

    final = balance(clean, rng, rejected)

    for s in SPLITS:
        part = [r for r in final if r["split"] == s]
        rng.shuffle(part)
        with open(DATA / f"{s}.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["text", "label", "category", "source", "injected_text"],
                               extrasaction="ignore")
            w.writeheader()
            # injected_text: el fragmento malicioso dentro de `text` (vacío en los legítimos).
            w.writerows({**r, "injected_text": r.get("injected_text") or ""} for r in part)
    with open(DATA / "rejected.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["reason", "split", "source", "label", "category", "text"], extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(rejected, key=lambda r: (r["reason"], r["source"])))
    try:  # manifiestos MCP (MCPTox + ToolACE), solo evaluación; se generan en local
        import manifests
        manifest_md = manifests.build(quality_issues, normalize)
    except Exception as e:
        manifest_md = f"\n## Manifiestos MCP\n\nNo generados ({e}).\n"
        print(f"AVISO: manifiestos MCP no generados ({e})", file=sys.stderr)
    (DATA / "QUALITY.md").write_text(report(final, rejected, n_input) + manifest_md, encoding="utf-8")

    from build_mcp import write_mcp  # casos MCP (prompt + respuesta) solo con filas aceptadas
    write_mcp(final)

    print(f"\n{'split':6} {'filas':>6} {'ataques':>8} {'legítimos':>10} {'hard_neg':>9}")
    for s in SPLITS:
        p = [r for r in final if r["split"] == s]
        a = sum(r["label"] == "attack" for r in p)
        print(f"{s:6} {len(p):6} {a:8} {len(p) - a:10} {sum(r['category'] == 'hard_negative' for r in p):9}")
    print(f"descartadas: {len(rejected)} (ver data/rejected.csv); reporte en data/QUALITY.md")


if __name__ == "__main__":
    main()
