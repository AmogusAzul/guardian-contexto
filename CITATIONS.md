# Citas y atribución

La hackathon exige citar todo código, dataset, librería o fragmento generado con IA. Se agrega aquí en el momento en que se usa.

| Qué | Fuente | Licencia | Dónde se usa |
|---|---|---|---|
| AgentDojo | https://github.com/ethz-spylab/agentdojo | MIT | `bench/` |
| MCPTox | https://github.com/zhiqiangwang4/MCPTox-Benchmark | sin licencia declarada; solo como datos | `bench/` (si se usa) |
| Documentación y mock inicial de `guard/check.py` | Generados con asistencia de IA (Claude) | — | `docs/`, `guard/` |
| Instrucciones para agentes del equipo (`CLAUDE.md`, `.claude/skills/`) | Generadas con Claude Code (claude-opus-5-5); sin revisar | — | `CLAUDE.md`, `.claude/skills/` |
| sentence-transformers | https://github.com/UKPLab/sentence-transformers | Apache-2.0 | `guard/embed.py` |
| all-MiniLM-L6-v2 | https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 | Apache-2.0 | `guard/` (modelo `minilm`, por defecto) |
| model2vec | https://github.com/MinishLab/model2vec | MIT | `guard/embed.py` |
| potion-base-8M | https://huggingface.co/minishlab/potion-base-8M | MIT | `guard/` (modelo `potion`) |
| PyTorch, NumPy | https://pytorch.org, https://numpy.org | BSD-3-Clause | `guard/` |
| Código del guardián v1 (`guard/`) y `data/seed.csv` (filas sintéticas) | Generados con asistencia de IA (Claude) | — | `guard/`, `data/seed.csv` |
