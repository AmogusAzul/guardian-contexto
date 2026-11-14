# bench/

Dueño: **Integración y benchmarks**. Ver `docs/evaluation.md` y el Contrato 2 de `docs/architecture.md`.

Va aquí:
- `agentdojo_guard.py`: las defensas `guard-detect` y `guard-sanitize` para AgentDojo.
- `keyword_detector.py`: la línea base de palabras clave.
- `run_agentdojo.py`: corre todas las defensas con el mismo modelo y tareas y escribe en `results/`.
- `eval_detector.py`: mide el guardián solo sobre `data/test.csv` (sin API).
- `demo.py`: un caso de AgentDojo con salida cruda contra salida limpia, para la ficha y el video.

La clave de OpenAI va en la variable de entorno `OPENAI_API_KEY`, nunca en el repo.
