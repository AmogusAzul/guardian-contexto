---
name: run-eval
description: Cómo correr la evaluación en bench/ (AgentDojo con todas las defensas y el detector solo sobre data/test.csv) para producir los números de la ficha contra las líneas base, sin contaminar el conjunto de prueba. Úsala al tocar bench/, al ajustar umbrales o al reportar cualquier número.
---

# Evaluación

Fuente de verdad: `docs/evaluation.md` y el Contrato 4 de `docs/architecture.md`. La rúbrica da 5 en ejecución a lo que "funciona de punta a punta, se puede reproducir y se evaluó contra una línea base".

## Niveles

1. **AgentDojo (principal):** mismo modelo y mismas tareas para todas las defensas; `banking` primero (skill `agentdojo-adapter`).
2. **Detector solo (sin API):** `data/test.csv`, trozos inyectados y legítimos de fuentes no usadas para entrenar (`bench/eval_detector.py`).
3. **MCPTox (si alcanza):** descripciones envenenadas y limpias con `origen="manifiesto"`.

## Líneas base (mismo modelo y tareas)

1. Sin defensa.
2. Filtro de palabras clave (otro `PromptInjectionDetector`, `bench/keyword_detector.py`).
3. Detector DeBERTa de AgentDojo (`transformers_pi_detector`).
4. Opcional: `tool_filter` o `spotlighting_with_delimiting`.

Nuestras variantes: `guard-detect` (descarta la salida) y `guard-sanitize` (retira solo los trozos).

## Procedimiento (en orden)

1. Construir el guardián solo con `train`.
2. Elegir los umbrales en `val`: los más bajos que dejen los falsos positivos en 5 % o menos. Comparar variantes aquí, nunca en `test` ni en AgentDojo.
3. Congelar modelo, umbrales y trozos. Anotar el commit.
4. Correr `test` y AgentDojo **una sola vez** con todas las defensas. Si después se cambia algo, se dice en la ficha.
5. Guardar en `results/` (abajo). El README trae el comando exacto.

## Salida (Contrato 4)

Cada corrida escribe `results/<fecha>-<commit>-<nombre>.json` y una línea en `results/summary.csv` con: defensa, modelo, suite, n de tareas, utilidad, utilidad bajo ataque, éxito del ataque, latencia mediana del guardián, tokens usados.

## Qué reporta

- Siempre con `n` e intervalo de Wilson al 95 %.
- Detección junto a falsos positivos; éxito del ataque junto a utilidad. Nunca uno sin el otro.
- Por categoría además del total; falsos positivos en hard negatives aparte.
- Latencia de `check()`: mediana y p95 (objetivo < 300 ms).
- Tokens por caso en AgentDojo (el guardián no gasta tokens).

## Reglas

- Un solo comando desde la terminal por nivel; semilla fija para todo lo aleatorio.
- **Ningún texto de AgentDojo** en entrenamiento ni umbrales.
- Ningún número entra a la ficha si no salió de un archivo en `results/`.
- Los números publicados de AgentDojo (GPT-4o) se citan solo como referencia; se compara contra nuestras corridas con el mismo modelo.
