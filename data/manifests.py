"""Descripciones de herramientas MCP (manifiestos) para evaluar `check(..., origen="manifiesto")`.

MCPTox (https://github.com/zhiqiangwang4/MCPTox-Benchmark) solo mide detección: trae 485
descripciones envenenadas de herramientas de 45 servidores MCP reales. Para medir FALSOS
POSITIVOS hacen falta descripciones limpias comparables:

- `mcptox_clean`: las descripciones reales y limpias de las herramientas de esos MISMOS 45
  servidores (vienen en el prompt limpio de `response_all.json` de MCPTox). Igual contra igual.
- `toolace_manifests`: descripciones de APIs reales de ToolACE (Apache-2.0,
  https://huggingface.co/datasets/Team-ACE/ToolACE). Las limpias de MCPTox son mucho más cortas
  que las envenenadas (mediana 53 vs 257 caracteres): un detector que marcara "lo largo" se vería
  excelente. Las de ToolACE se eligen para EMPAREJAR la longitud de las envenenadas.
- `mcptox_poisoned`: las 485 envenenadas (detección).

Salida: data/mcp_manifests.jsonl (val y test; NO hay train: es material de evaluación).
Split por SERVIDOR en MCPTox (limpias y envenenadas de un servidor van juntas) y por nombre de
API en ToolACE.

IMPORTANTE: MCPTox no declara licencia y sus descripciones envenenadas contienen payloads
funcionales. El archivo de salida se genera en local y NO se sube a git (.gitignore). Solo se
sube la muestra de ToolACE (data/pools/toolace_descriptions.jsonl).
"""

from __future__ import annotations

import bisect
import collections
import json
import random
import re
import statistics
from pathlib import Path

from sources import POOLS, RAW, _download, diverse_sample, stable_bucket

DATA = Path(__file__).resolve().parent
MCPTOX = "https://raw.githubusercontent.com/zhiqiangwang4/MCPTox-Benchmark/main/"
TOOLACE = "https://huggingface.co/datasets/Team-ACE/ToolACE/resolve/main/data.json"

_TOOL_BLOCK = re.compile(r"Tool: (.+?)\nDescription: (.*?)\nArguments:\n(.*?)(?=\n\n\nTool: |\Z)", re.S)
# Artefacto de ToolACE: reemplazaron "date" por "string" dentro de palabras ("upstringd" = "updated").
_TOOLACE_ARTIFACT = re.compile(r"\b\w*string\w*\b", re.I)
_OK_STRING = {"string", "strings", "substring", "substrings", "querystring", "tostring", "bitstring"}
# Descripciones legítimas que dan órdenes o advierten (el estilo de las envenenadas): hard negatives.
_ARGS_ARTIFACT = re.compile(r"(\s|\\n)*Arguments:(\s|\\n).*$", re.S)
# ("required" no cuenta: aparece en los esquemas de parámetros, no es una orden)
_IMPERATIVE = re.compile(r"\b(must|do not|don't|never|always|before|important|ignore|password|"
                         r"credentials?|token|please|warning|caution)\b", re.I)


def _snake(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _server_split(server: str) -> str:
    return "val" if stable_bucket(server.lower(), 3) == 0 else "test"


def mcptox_rows() -> list[dict]:
    resp = json.load(open(_download(MCPTOX + "response_all.json", RAW / "mcptox" / "response_all.json"), encoding="utf-8"))
    pure = json.load(open(_download(MCPTOX + "pure_tool.json", RAW / "mcptox" / "pure_tool.json"), encoding="utf-8"))
    rows = []
    for s in resp["servers"].values():
        server = s["server_name"]
        queries = s.get("clean_querys") or []
        for m in _TOOL_BLOCK.finditer(s["clean_system_promot"]):
            desc = m.group(2).strip()
            rows.append(dict(text=desc, label="benign",
                             category="hard_negative" if _IMPERATIVE.search(desc) else "clean_manifest",
                             source="mcptox_clean", server=server, tool_name=m.group(1).strip(),
                             arguments=m.group(3).strip(), query=queries[0] if queries else None,
                             split=_server_split(server)))
    for block in pure:
        for v in block.values():
            # Resto del formato de MCPTox en ~la mitad de las envenenadas (las limpias nunca lo
            # tienen): "\nArguments:\n- No arguments\n\n\n" con \n literales. Sería un atajo perfecto.
            text = _ARGS_ARTIFACT.sub("", v["tool_content"]).replace("\\n", "\n").strip()
            rows.append(dict(text=text, label="attack",
                             category=_snake(v["security risk"]), source="mcptox_poisoned",
                             server=v["server_name"], tool_name=v["tool_name"], query=v["query"],
                             paradigm=v["paradigm"], split=_server_split(v["server_name"])))
    return rows


def build_toolace_pool(n: int = 1200, min_chars: int = 120) -> Path:
    """Descripciones largas, sin el artefacto "string", diversas."""
    out = POOLS / "toolace_descriptions.jsonl"
    if out.exists():
        return out
    data = json.load(open(_download(TOOLACE, RAW / "toolace.json"), encoding="utf-8"))
    descs = {}
    for it in data:
        m = re.search(r"you can invoke:\n(\[.*\])", it.get("system", ""), re.S)
        if not m:
            continue
        try:  # la lista JSON va seguida de más texto: leer solo el primer valor
            fs, _ = json.JSONDecoder().raw_decode(m.group(1))
        except Exception:
            continue
        for f in fs:
            d = (f.get("description") or "").strip() if isinstance(f, dict) else ""
            if len(d) >= min_chars and not any(w.lower() not in _OK_STRING for w in _TOOLACE_ARTIFACT.findall(d)):
                descs.setdefault(d, f.get("name", ""))
    keep = diverse_sample(list(descs), n, max_jaccard=0.5, rng=random.Random(9))
    POOLS.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        for d in keep:
            fh.write(json.dumps({"tool_name": descs[d], "text": d}, ensure_ascii=False) + "\n")
    return out


def toolace_rows(target_lengths: list[int], rng: random.Random, used: set) -> list[dict]:
    """Elige descripciones de ToolACE cuya distribución de largo imite la de las envenenadas:
    para cada largo objetivo, la descripción disponible más cercana."""
    pool = [json.loads(l) for l in open(build_toolace_pool(), encoding="utf-8")]
    pool.sort(key=lambda x: len(x["text"]))
    lens = [len(x["text"]) for x in pool]
    rows = []
    for t in target_lengths:
        # búsqueda del más cercano no usado
        i = bisect.bisect_left(lens, t)
        for j in sorted(range(max(0, i - 40), min(len(pool), i + 40)), key=lambda k: abs(lens[k] - t)):
            if j not in used:
                used.add(j)
                x = pool[j]
                rows.append(dict(text=x["text"], label="benign",
                                 category="hard_negative" if _IMPERATIVE.search(x["text"]) else "clean_manifest",
                                 source="toolace_manifests", server="toolace", tool_name=x["tool_name"],
                                 split="val" if stable_bucket(x["tool_name"] + x["text"][:20], 3) == 0 else "test"))
                break
    return rows


def build(quality_issues, normalize) -> str:
    """Genera data/mcp_manifests.jsonl y devuelve la sección de QUALITY.md. Los descartes NO van a
    rejected.csv (que se sube a git) porque llevarían texto de MCPTox: solo se cuentan."""
    rejected: list[dict] = []
    rng = random.Random(13)

    def clean(rows: list[dict], seen: set) -> list[dict]:
        kept = []
        for r in rows:
            r = dict(r, text=normalize(r["text"]))
            # Las descripciones reales pueden ser cortas ("Get weather"): basta con 2 palabras.
            issues = [i for i in quality_issues(r) if i != "too_short"]
            if len(re.findall(r"\w+", r["text"])) < 2:
                issues.append("too_short")
            key = re.sub(r"\s+", " ", r["text"].lower())
            if not issues and key in seen:
                issues = ["exact_duplicate"]
            if issues:
                rejected.append(dict(r, reason="+".join(issues)))
                continue
            seen.add(key)
            kept.append(r)
        return kept

    seen: set = set()
    used: set = set()  # índices de ToolACE ya elegidos (val y test no comparten)
    kept = clean(mcptox_rows(), seen)
    # Completar con ToolACE hasta 50/50 por split, imitando el largo de las envenenadas del split.
    for s in ("val", "test"):
        pois = [len(r["text"]) for r in kept if r["split"] == s and r["label"] == "attack"]
        n_clean = sum(1 for r in kept if r["split"] == s and r["label"] == "benign")
        k = max(0, len(pois) - n_clean)
        extra = toolace_rows(rng.sample(pois, min(k, len(pois))), rng, used)
        kept += clean([dict(r, split=s) for r in extra], seen)

    with open(DATA / "mcp_manifests.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for i, r in enumerate(kept):
            f.write(json.dumps(dict(id=f"manifest-{i:04d}", **r), ensure_ascii=False) + "\n")

    # Sección del reporte
    L = ["\n## Manifiestos MCP (`mcp_manifests.jsonl`, solo evaluación)\n",
         "Para `check(texto, origen=\"manifiesto\")`. Se genera en local (MCPTox no declara licencia y trae payloads funcionales: no se sube).\n",
         "| Split | Fuente | Envenenadas | Limpias | Hard negatives | Largo mediano |", "|---|---|---|---|---|---|"]
    for s in ("val", "test"):
        for src in ("mcptox_poisoned", "mcptox_clean", "toolace_manifests"):
            rs = [r for r in kept if r["split"] == s and r["source"] == src]
            if rs:
                a = sum(r["label"] == "attack" for r in rs)
                h = sum(r["category"] == "hard_negative" for r in rs)
                L.append(f"| {s} | {src} | {a} | {len(rs) - a} | {h} | {statistics.median(len(r['text']) for r in rs):.0f} |")
    from pipeline import _auc
    A = [len(r["text"]) for r in kept if r["label"] == "attack"]
    B_all = [len(r["text"]) for r in kept if r["label"] == "benign"]
    B_mcp = [len(r["text"]) for r in kept if r["source"] == "mcptox_clean"]
    L.append(f"\nAUC de la longitud (0,5 = no ayuda): envenenadas vs todas las limpias **{_auc(A, B_all):.2f}**; "
             f"envenenadas vs solo limpias de MCPTox **{_auc(A, B_mcp):.2f}**. Reportar los falsos positivos "
             "por fuente: los de `mcptox_clean` son el caso real, los de `toolace_manifests` controlan el atajo de longitud.\n")
    rej = collections.Counter((r["source"], r["reason"]) for r in rejected)
    L.append("Descartes: " + (", ".join(f"{s} / {why}: {n}" for (s, why), n in sorted(rej.items())) or "ninguno") + ".\n")
    risks = collections.Counter(r["category"] for r in kept if r["label"] == "attack")
    L.append("Riesgos en las envenenadas: " + ", ".join(f"{k} ({v})" for k, v in risks.most_common()) + ".\n")
    return "\n".join(L)
