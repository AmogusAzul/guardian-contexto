---
name: agentdojo-adapter
description: Cómo conectar el guardián a AgentDojo (ETH Zürich) con las dos defensas guard-detect y guard-sanitize, y correr una evaluación pequeña y barata con la clave de OpenAI. Úsala al instalar AgentDojo, escribir los adaptadores en bench/ o interpretar sus resultados.
---

# AgentDojo

Benchmark principal (Track 1): agentes con herramientas en entornos simulados (`banking`, `workspace`, `slack`, `travel`) atacados con inyección indirecta en lo que devuelven las herramientas. Licencia MIT. Docs: https://agentdojo.spylab.ai/. Fuente de verdad: Contrato 2 en `docs/architecture.md` y `docs/evaluation.md`.

La clave va en `OPENAI_API_KEY`, nunca en el repo. Poner un límite de gasto en la cuenta.

## Instalar y probar

```bash
pip install agentdojo                     # y "agentdojo[transformers]" para el detector DeBERTa
python -m agentdojo.scripts.benchmark --help
python -m agentdojo.scripts.benchmark -s banking -ut user_task_0 -ut user_task_1 \
    --model <modelo> --attack important_instructions          # sin defensa
```

Empezar con `banking` y 2 tareas × 2 inyecciones para medir tokens por caso; luego la suite completa. **Todas las defensas con el mismo modelo** (por ejemplo `gpt-4o-mini`): la tabla publicada usa `gpt-4o-2024-05-13` y no es comparable directamente.

## Las dos defensas (en `bench/`)

La `tarea` que se pasa a `check()` es el **primer mensaje del usuario** de la conversación.

Implementadas en `bench/agentdojo_guard.py` (probadas con agentdojo 0.1.35, benchmark v1.2.2):

- **`guard-detect`** (`GuardDetect`): subclase de `PromptInjectionDetector`. AgentDojo descarta la salida completa cuando detecta algo. Comparable uno a uno con DeBERTa.
- **`guard-sanitize`** (`GuardSanitize`): hereda de `GuardDetect` y sobrescribe `transform()` para devolver `info["texto_limpio"]` en vez de descartar. Es la tesis: sanear en vez de descartar.

Las dos llaman `check()` con la misma tarea, así que la única diferencia es descartar frente a sanear. Si `guard-sanitize` conserva más utilidad bajo ataque que `guard-detect` con un éxito del ataque parecido, la tesis queda demostrada.

## Cómo funciona AgentDojo por dentro (verificado en el código, 0.1.35)

- `PromptInjectionDetector.query()` recorre los mensajes `tool` del final de la conversación, llama `detect(texto)` en cada uno y, si da `True`, reemplaza el contenido con `transform(contenido)` (por defecto `"<Data omitted because a prompt injection was detected>"`). `transform()` se llama justo después de `detect()` sobre el mismo mensaje.
- `detect()` solo recibe el texto. La tarea se toma en `query()`, que recibe el prompt del usuario como primer argumento (y está en el primer mensaje `user`): `GuardDetect` la guarda ahí antes de llamar al padre.
- `--defense` del CLI solo acepta las defensas de serie: por eso `bench/run_agentdojo.py` arma el `AgentPipeline` a mano.
- El nombre del pipeline debe contener el id del modelo (p. ej. `gpt-4o-mini-2024-07-18`): `important_instructions` lo usa para dirigirse al modelo ("to you, GPT-4") y falla si no lo encuentra.
- Las salidas de herramientas son YAML (`yaml.safe_dump`); la plantilla `important_instructions` mete el ataque con saltos de línea dentro de un campo.
- En los resultados, `security_results = True` significa que **el ataque tuvo éxito**.
- `benchmark_suite_with_injections` también corre las injection tasks como tareas de usuario (para comprobar que son posibles): por eso hay más salidas revisadas que casos.

## Comandos

```bash
python -m pytest tests                                   # adaptadores, sin API
python -m bench.run_agentdojo --offline -s banking -ut user_task_0 -it injection_task_0   # integración, sin API
python -m bench.run_agentdojo -s banking -ut user_task_0 -ut user_task_1 -it injection_task_0 -it injection_task_1
```

## Línea base publicada (gpt-4o-2024-05-13, ataque important_instructions)

| Defensa | Utilidad | Utilidad bajo ataque | Éxito del ataque |
|---|---|---|---|
| Ninguna | 69,1 % | 50,1 % | 47,7 % |
| tool_filter | 72,2 % | 56,3 % | 6,8 % |
| Detector DeBERTa (transformers_pi_detector) | 41,2 % | 21,1 % | 8,0 % |

Solo como referencia: verificar en https://agentdojo.spylab.ai/results/ antes de citar y comparar contra nuestras propias corridas con el mismo modelo.

**Ningún texto de AgentDojo** entra al entrenamiento ni a los umbrales: es el examen final.
