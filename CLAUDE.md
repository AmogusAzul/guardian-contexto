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
              check() en __init__.py encadena chunking → embedding → attack + drift → decision → rebuild
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
2. **Contrato del guardián** (Contrato 1, skill `guard-contract`): `check(texto: str, tarea: str | None = None, origen: str = "herramienta", herramienta: ToolCall | None = None) -> tuple[bool, dict]`. `info` lleva `texto_limpio`, `trozos_marcados` (cada uno con `texto`, `tipo`, `ruta`, `attack_score`, `drift_score`), `attack_score`, `drift_score`, `latencia_ms` y `origen` (`herramienta`, `manifiesto` o `usuario`). Cambiarlo requiere avisar en un checkpoint.
3. **`check()` va sobre cada salida de herramienta**, justo después de ejecutarla y antes de que vuelva al LLM. La `tarea` son los mensajes del usuario de la conversación; `herramienta` es la llamada que produjo la salida (nombre, descripción, argumentos). Las descripciones de herramientas (MCPTox) se revisan con `origen="manifiesto"`.
4. **Citar todo** (skill `cite`): cada dependencia, dataset, modelo y archivo escrito con IA entra a `CITATIONS.md` **en el mismo cambio**. Es una regla del hackathon.
5. **Uso responsable** (skill `responsible-use`): nada contra sistemas reales, ningún exploit funcional, solo datos sintéticos o públicos anonimizados. Los payloads de los benchmarks son texto: nunca se ejecutan.
6. **Los números salen de `results/`,** nunca de ejemplos elegidos a mano. El conjunto de prueba y AgentDojo se corren una sola vez con el guardián congelado (skill `run-eval`). **Ningún texto de AgentDojo** entra al entrenamiento ni a la elección de umbrales.
7. Primero la versión fea de punta a punta, después se mejora. Si algo bloquea a otro rol, se trabaja contra el mock del guardián (`guard/mock.py`, activo con `GUARD_MOCK=1`), que tiene la firma final.

## Comandos

```sh
uv pip install -e ".[guard]"   # torch para CPU: uv pip install torch --index-url https://download.pytorch.org/whl/cpu
GUARD_MOCK=1 ...               # usa el mock sin dependencias (los pasos de guard/ aún no están escritos)
```

Integración agrega aquí y en el README las pruebas, AgentDojo con cada defensa y la evaluación del detector.

## Preguntas abiertas (decidir en un checkpoint)

Ya resueltas en [docs/algorithm.md](docs/algorithm.md): trozos sobre la estructura (valores, rutas y claves), desvío con tres referencias y percentiles, falsos positivos por salida, retirar el campo o la rama. Siguen abiertas:

- **Contrato 3:** filas con salidas completas en contexto (propuesta en `docs/architecture.md`). Datos tiene que aceptarla antes de generar.
- **Ataques de AgentDojo:** ¿correr además de `important_instructions` otro ataque (`ignore_previous`, `tool_knowledge`) para no medir una sola plantilla?

## Idioma

Código, nombres de archivos y commits en inglés, salvo los nombres del contrato que ya están en español (`permitido`, `tarea`, `origen`, `texto_limpio`, `trozos_marcados`). Ficha y documentación del equipo en español. Los datos y la evaluación están en inglés (AgentDojo).
