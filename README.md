# Guardián de prompts con embeddings

Proyecto para la Hackathon AI Safety Colombia ([aisafetycolombia.org/defacchackathon](https://aisafetycolombia.org/defacchackathon)).

**Visión:** un filtro rápido y casi determinista, basado en embeddings, que bloquea antes del LLM los mensajes que intentan abusar de las capacidades de un agente (prompt injection) o gastar tokens en temas ajenos al chatbot.

**Funciones previstas:** puntaje de ataque y de tema por mensaje, veredicto (`allow` / `block_attack` / `block_off_topic`), trozo sospechoso resaltado, y evaluación contra un filtro de palabras clave.

## Documentos

- [docs/one-page-plan.md](docs/one-page-plan.md) — plan de arranque: roles, contratos, demo, reglas ([versión imprimible](docs/one-page-plan.html)).
- [docs/business-brief.md](docs/business-brief.md) — Colibrí Code, el negocio ficticio de la demo: cursos, capacidades del agente, textos e identidad visual.
- [docs/algorithm-risks.md](docs/algorithm-risks.md) — por qué el algoritmo podría fallar y cómo hacerlo funcionar.
- [docs/latex/](docs/latex/) — los tres documentos en LaTeX (una página cada uno). Compilar con `docs/latex/build.sh` (LuaLaTeX + latexmk; Chrome/Chromium para convertir el diagrama, o `CHROME=/ruta ./build.sh`).
