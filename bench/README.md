# bench/

Dueño: **Integración y benchmarks**. Ver `docs/evaluation.md`, el Contrato 2 de `docs/architecture.md` y el skill `agentdojo-adapter`.

| Archivo | Qué |
|---|---|
| `agentdojo_guard.py` | las defensas `guard-detect` (`GuardDetect`) y `guard-sanitize` (`GuardSanitize`) para AgentDojo |
| `keyword_detector.py` | la línea base de palabras clave (sin marcas propias de AgentDojo) |
| `run_agentdojo.py` | corre todas las defensas con el mismo modelo, suite y tareas; escribe en `results/` |

Pendiente: `eval_detector.py` (el guardián solo sobre `data/test.csv`, sin API) y `demo.py`.

## Uso

```sh
pip install -e ".[guard,bench]"          # torch para CPU primero: pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pytest tests                   # adaptadores con un check() falso: sin API ni modelo

# integración de punta a punta SIN API: el "LLM" ejecuta las llamadas de referencia de cada tarea.
# Solo comprueba que todo corre; escribe en runs/offline/, no en results/.
python -m bench.run_agentdojo --offline -s banking -ut user_task_0 -it injection_task_0

# piloto con OpenAI (medir tokens por caso antes de la suite completa)
python -m bench.run_agentdojo -s banking -ut user_task_0 -ut user_task_1 -it injection_task_0 -it injection_task_1

# una suite completa con las 5 defensas (none, keyword, transformers_pi_detector, guard-detect, guard-sanitize)
python -m bench.run_agentdojo -s banking
```

Opciones útiles: `-d <defensa>` (repetible), `--modelo`, `--ataque`, `--sin-utilidad`, `--force-rerun`. `GUARD_MODEL=potion` cambia el modelo de embeddings del guardián.

Cada defensa escribe `results/<fecha>-<commit>-agentdojo-<suite>-<defensa>.json` y una línea en `results/summary.csv`. Las trazas completas quedan en `runs/` (no se versiona). Si se repite un comando, AgentDojo reutiliza los casos ya corridos: no se pagan dos veces, pero esos casos no suman tokens ni latencias del guardián (el JSON lo dice). Para una corrida limpia y completa, `--force-rerun` o un `--logdir` nuevo.

## Claves y modelos

Las claves van en `.env` en la raíz (está en `.gitignore`), nunca en el repo:

```
OPENAI_API_KEY=sk-...          # modelos de OpenAI (por defecto gpt-4o-mini-2024-07-18)
GEMINI_API_KEY=AIza...         # modelos de Gemini con clave de AI Studio: --modelo gemini-...
```

Con `--modelo gemini-…` el script crea el cliente con la clave de AI Studio (el CLI de AgentDojo solo usa Vertex AI), registra el modelo para que el ataque pueda nombrarlo ("AI model developed by Google", la misma frase que AgentDojo usa para Gemini) y reintenta los errores 429 de límite de peticiones, que AgentDojo no reintenta. **Todas las defensas deben correrse con el mismo modelo.**
