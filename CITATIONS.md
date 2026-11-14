# Citas y atribución

La hackathon exige citar todo código, dataset, librería o fragmento generado con IA. Se agrega aquí en el momento en que se usa.

| Qué | Fuente | Licencia | Dónde se usa |
|---|---|---|---|
| AgentDojo | https://github.com/ethz-spylab/agentdojo | MIT | `bench/` |
| MCPTox (Wang et al., 2025): descripciones envenenadas y descripciones limpias reales de los 45 servidores | https://github.com/zhiqiangwang4/MCPTox-Benchmark | sin licencia declarada; solo como datos, **no se redistribuye** (se descarga al generar) | `data/mcp_manifests.jsonl` (local), `bench/` |
| ToolACE (Liu et al., 2024): descripciones de APIs | https://huggingface.co/datasets/Team-ACE/ToolACE | Apache-2.0 | `data/pools/toolace_descriptions.jsonl`, `data/mcp_manifests.jsonl` |
| LLMail-Inject (Abdelnabi et al., Microsoft, 2025): ataques humanos `api_triggered` y correos legítimos | https://huggingface.co/datasets/microsoft/llmail-inject-challenge | MIT | `data/*.csv`, `data/mcp_*.jsonl`, `data/pools/` (destino `contact@contact.com` reemplazado por correos ficticios) |
| InjecAgent (Zhan et al., ACL Findings 2024): plantillas de respuestas de herramientas e instrucciones del atacante | https://github.com/uiuc-kang-lab/InjecAgent | MIT | `data/*.csv`, `data/mcp_*.jsonl` (correos del atacante reemplazados por ficticios) |
| NotInject (InjecGuard, Li y Liu, 2024): legítimos con palabras gatillo | https://huggingface.co/datasets/leolee99/NotInject | MIT | `data/val.csv`, `data/test.csv` (solo evaluación de sobre-defensa) |
| Glaive Function Calling v2: respuestas de funciones con su petición | https://huggingface.co/datasets/glaiveai/glaive-function-calling-v2 | Apache-2.0 | `data/*.csv`, `data/mcp_*.jsonl`, `data/pools/` |
| Plantillas sintéticas de salidas de herramientas, hard negatives e inyecciones (`data/build.py`), contenido legítimo para las plantillas de InjecAgent (`data/sources.py`) | Escritas con asistencia de IA (Claude) y revisadas por el equipo | — | `data/*.csv`, `data/mcp_*.jsonl` |
| Canalización de calidad del corpus (`data/pipeline.py`, `data/sources.py`, `data/build_mcp.py`, `data/manifests.py`) | Generada con asistencia de IA (Claude) | — | `data/` |
| Ataques en claves JSON y sus hard negatives (`data/key_attacks.py`): frases y claves escritas con asistencia de IA (Claude), insertadas en respuestas de Glaive e InjecAgent | Generados con asistencia de IA (Claude) | — | `data/*.csv`, `data/mcp_*.jsonl` |
| deepset/prompt-injections (evaluado y **descartado**: estilo de chat, etiquetas ruidosas, filas en alemán) | https://huggingface.co/datasets/deepset/prompt-injections | Apache-2.0 | no se usa |
| Documentación y mock inicial de `guard/check.py` | Generados con asistencia de IA (Claude) | — | `docs/`, `guard/` |
| Instrucciones para agentes del equipo (`CLAUDE.md`, `.claude/skills/`) | Generadas con Claude Code (claude-opus-5-5); sin revisar | — | `CLAUDE.md`, `.claude/skills/` |
| sentence-transformers | https://github.com/UKPLab/sentence-transformers | Apache-2.0 | `guard/embed.py` |
| all-MiniLM-L6-v2 | https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 | Apache-2.0 | `guard/` (modelo `minilm`, por defecto) |
| model2vec | https://github.com/MinishLab/model2vec | MIT | `guard/embed.py` |
| potion-base-8M | https://huggingface.co/minishlab/potion-base-8M | MIT | `guard/` (modelo `potion`) |
| PyTorch, NumPy | https://pytorch.org, https://numpy.org | BSD-3-Clause | `guard/` |
| Código del guardián v1 (`guard/`) y `data/seed.csv` (filas sintéticas) | Generados con asistencia de IA (Claude) | — | `guard/`, `data/seed.csv` |
