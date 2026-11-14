# Guardián de contexto (Hackathon DefAcc, Track 1)

Guardián basado en embeddings que revisa lo que **devuelven las herramientas** (servidores MCP, APIs, documentos) **antes** de que entre al contexto del LLM, y retira solo los trozos con instrucciones maliciosas. La amenaza es la **inyección indirecta** (Track 1: "Seguridad de agentes"). Se evalúa en **AgentDojo** con la clave de OpenAI, contra sin defensa, un filtro de palabras clave y el detector DeBERTa.

Hackathon de un día (sábado 14 de noviembre de 2026, de 9:00 a 17:00). Prioridad: algo que funcione de punta a punta y números reproducibles, no código elegante.

## Documentos (fuente de verdad)

Viven en `docs/` (Markdown, para personas y agentes; si el PDF difiere, gana el Markdown):

- `docs/idea.md`: amenaza, defensa, límites y uso dual.
- `docs/architecture.md`: flujo, estructura y **contratos** (1 `check()`, 2 adaptador de AgentDojo, 3 datasets, 4 resultados).
- `docs/algorithm.md`: cómo funciona el guardián (versión 1 y 2) y cómo podría fallar.
- `docs/evaluation.md`: benchmarks, datos, métricas, líneas base y procedimiento.
- `docs/team.md`: roles (Algoritmo, Datos, Integración y benchmarks, Pitch), cronograma por bloques y checkpoints.
- `docs/pitch.md`: ficha técnica, resumen, guion y preguntas probables.
- `docs/hackathon.md`: reto, rúbrica, horarios, entregables y reglas.
- `docs/latex/main.pdf`: versión para leer del plan.

Si el código y estos documentos no coinciden, se avisa al equipo; no se cambia un contrato en silencio.

## Estructura del repo

```
guard/        paquete del guardián (Algoritmo). Python puro, sin dependencias de AgentDojo.
bench/        adaptadores y evaluación (Integración): guard-detect, guard-sanitize, palabras clave, AgentDojo, demo.py
data/         datasets del Contrato 3 (Datos): train.csv, val.csv, test.csv
results/      salidas de la evaluación con fecha y commit (Contrato 4); de aquí salen los números de la ficha
docs/         documentación del equipo (fuente de verdad) y docs/latex/ (PDF)
.claude/      skills para los agentes del equipo
CITATIONS.md  todo el código, datos, librerías y texto generado con IA
README.md     qué es, cómo instalar y el comando exacto de la evaluación
```

## Reglas que no se rompen

1. **`guard/` es Python puro:** no importa AgentDojo, ni `bench/`, ni llama a un LLM. Lo usan `bench/` y cualquier proxy MCP.
2. **Contrato del guardián** (Contrato 1, skill `guard-contract`): `check(texto: str, tarea: str | None = None, origen: str = "herramienta") -> tuple[bool, dict]`. `info` lleva `texto_limpio`, `trozos_marcados` (cada uno con `texto`, `attack_score`, `drift_score`), `attack_score`, `drift_score`, `latencia_ms` y `origen` (`herramienta`, `manifiesto` o `usuario`). Cambiarlo requiere avisar en un checkpoint.
3. **`check()` va sobre cada salida de herramienta**, justo después de ejecutarla y antes de que vuelva al LLM. La `tarea` es el primer mensaje del usuario de la conversación. Las descripciones de herramientas (MCPTox) se revisan con `origen="manifiesto"`.
4. **Citar todo** (skill `cite`): cada dependencia, dataset, modelo y archivo escrito con IA entra a `CITATIONS.md` **en el mismo cambio**. Es una regla del hackathon.
5. **Uso responsable** (skill `responsible-use`): nada contra sistemas reales, ningún exploit funcional, solo datos sintéticos o públicos anonimizados. Los payloads de los benchmarks son texto: nunca se ejecutan.
6. **Los números salen de `results/`,** nunca de ejemplos elegidos a mano. El conjunto de prueba y AgentDojo se corren una sola vez con el guardián congelado (skill `run-eval`). **Ningún texto de AgentDojo** entra al entrenamiento ni a la elección de umbrales.
7. Primero la versión fea de punta a punta, después se mejora. Si algo bloquea a otro rol, se trabaja contra el mock del guardián (`guard/mock.py`, activo con `GUARD_MOCK=1`), que tiene la firma final.

## Comandos

```sh
uv pip install -e ".[guard]"   # torch para CPU: uv pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m guard.train          # ajusta el guardián con data/train.csv + data/val.csv (o data/seed.csv); escribe guard/artifacts/<modelo>.json
GUARD_MOCK=1 ...               # usa el mock sin dependencias
uv pip install -e ".[guard,bench]"   # AgentDojo 0.1.35 + DeBERTa + pytest
python -m pytest tests         # adaptadores de AgentDojo con un check() falso (sin API ni modelo)
python -m bench.run_agentdojo --offline -s banking -ut user_task_0 -it injection_task_0   # integración sin API (runs/offline/)
python -m bench.run_agentdojo -s banking   # las 5 defensas con OpenAI -> results/ (ver bench/README.md)
```

Integración agrega aquí y en el README la evaluación del detector (`bench/eval_detector.py`).

## Preguntas abiertas (decidir en un checkpoint)

Salieron de una revisión del algoritmo; **no son decisiones todavía**:

- **`drift_score`:** el Contrato 3 no tiene columna de tarea, así que `τ_drift` no se puede elegir en validación sin AgentDojo; además las salidas legítimas suelen estar "lejos" de la tarea y las inyecciones de AgentDojo suelen ser del mismo dominio. ¿Agregar una columna `task` a validación, o empezar solo con `attack_score`?
- **Unidad de los falsos positivos:** ¿el 5 % se mide por trozo o por salida completa? Con ventanas que se solapan, 5 % por trozo es mucho más por salida.
- **Trozos:** las salidas de AgentDojo son listas tipo YAML/JSON, no prosa. ¿Partir primero por líneas, campos o elementos y luego por oraciones?
- **Saneo:** si se marca una parte de un campo o párrafo, ¿se retira el campo entero para no dejar restos del ataque?
- **Regresión logística en la versión 1:** ¿entrenarla junto a la resta de promedios y escoger en validación?
- **Ataques de AgentDojo:** ¿correr además de `important_instructions` otro ataque (`ignore_previous`, `tool_knowledge`) para no medir una sola plantilla?

## Idioma

Código, nombres de archivos y commits en inglés, salvo los nombres del contrato que ya están en español (`permitido`, `tarea`, `origen`, `texto_limpio`, `trozos_marcados`). Ficha y documentación del equipo en español. Los datos y la evaluación están en inglés (AgentDojo).
