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

- **`guard-detect`**: subclase de `PromptInjectionDetector`. AgentDojo descarta la salida completa cuando detecta algo. Comparable uno a uno con DeBERTa.

  ```python
  from agentdojo.agent_pipeline import PromptInjectionDetector
  from guard import check

  class GuardDetector(PromptInjectionDetector):
      def detect(self, tool_output: str):
          permitido, info = check(tool_output, tarea=self.tarea, origen="herramienta")
          return (not permitido), info["attack_score"]   # True = inyección
  ```

- **`guard-sanitize`**: un elemento del pipeline justo después de `ToolsExecutor` que reemplaza el contenido del mensaje de la herramienta por `info["texto_limpio"]`. Es la tesis: sanear en vez de descartar.

```python
pipeline = AgentPipeline([
    SystemMessage(...), InitQuery(), llm,
    ToolsExecutionLoop([ToolsExecutor(), GuardSanitizer(), llm]),
])
```

Si `guard-sanitize` conserva más utilidad bajo ataque que `guard-detect` con un éxito del ataque parecido, la tesis queda demostrada.

## Sin verificar (comprobarlo en el bloque 1, antes de depender de esto)

- Cómo se registra una defensa propia para `--defense` (probablemente hay que armar el `AgentPipeline` a mano o editar el script).
- De dónde sacar la tarea del usuario dentro de `detect()` (los mensajes o el `query` que recibe el elemento del pipeline).
- Qué hace exactamente AgentDojo con una detección positiva.

## Línea base publicada (gpt-4o-2024-05-13, ataque important_instructions)

| Defensa | Utilidad | Utilidad bajo ataque | Éxito del ataque |
|---|---|---|---|
| Ninguna | 69,1 % | 50,1 % | 47,7 % |
| tool_filter | 72,2 % | 56,3 % | 6,8 % |
| Detector DeBERTa (transformers_pi_detector) | 41,2 % | 21,1 % | 8,0 % |

Solo como referencia: verificar en https://agentdojo.spylab.ai/results/ antes de citar y comparar contra nuestras propias corridas con el mismo modelo.

**Ningún texto de AgentDojo** entra al entrenamiento ni a los umbrales: es el examen final.
