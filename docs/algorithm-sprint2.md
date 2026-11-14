# Algoritmo: segundo sprint

Ajustes que se dejan para después de tener la primera versión funcionando de punta a punta. Cada uno dice qué cambia, por qué y cómo se decide. Se agregan aquí; no se hacen hasta que la primera versión tenga números en `results/`.

## 1. `drift_score`: de máximo a promedio ponderado

**Hoy (primera versión):** el desvío toma la referencia que mejor encaja con el trozo:

```
drift = 1 − max(p_pedido, p_herramienta, p_vecinos)
```

donde cada `p` es la similitud del trozo con esa referencia, ya calibrada a percentil (ver [algorithm.md](algorithm.md)). Basta con parecerse a una referencia para estar “en contexto”.

**Problema:** el máximo es permisivo. Una inyección solo tiene que parecerse a una de las tres (por ejemplo, hablar de pagos en una herramienta de pagos) para pasar.

**Cambio:** un promedio ponderado,

```
drift = 1 − (w_pedido · p_pedido + w_herramienta · p_herramienta + w_vecinos · p_vecinos) / Σ w
```

con pesos aprendidos en validación (por ejemplo, una regresión logística sobre los tres percentiles y `attack_score`), sumando solo las referencias disponibles.

**Cómo se decide:** se compara contra el máximo en validación, a la misma tasa de falsos positivos por salida. Se adopta solo si detecta más. Más pesos son más cosas que ajustar con pocos datos: si validación es chica, gana el máximo.

## 2. Modelo de embeddings

Hoy: `all-MiniLM-L6-v2`. Comparar en validación con `BAAI/bge-small-en-v1.5` (lee más, suele separar mejor, algo más lento) y `potion-base-8M` (model2vec, estático, unas 10 veces más rápido, peor calidad; la salida si la latencia no alcanza). **Se decide con dos números:** AUC de la dirección de ataque por tipo de trozo y latencia de un `check()` (mediana y p95, < 300 ms). Gana el que mejor separa dentro del presupuesto de latencia.

## 3. Más datos de entrenamiento

`data/train.csv` tiene unos 784 ataques frente a 188 de `mcp_train.jsonl`, pero sin marcar qué parte es la inyección. Recuperarlos: 471 de esas filas contienen un `injected_text` conocido (marcar por coincidencia), los correos de LLMail son ataque enteros, y para el resto pedir a Datos la columna con el texto inyectado.

## 4. Mejor dirección de ataque

- **Regresión logística** sobre los embeddings en vez de la resta de promedios: el mismo tipo de modelo (un vector de pesos y un umbral), mejor dirección.
- **Vecinos cercanos:** `attack_score` = similitud con la inyección más cercana − similitud con el legítimo más cercano. Los *hard negatives* hacen de contrapeso y la explicación sale gratis (“se parece a este ataque conocido”).

Se decide igual que el punto 1: en validación, a la misma tasa de falsos positivos por salida.

## 5. Señal de “orden dirigida al asistente”

Trozos que le hablan al modelo (“Assistant:”, “AI, please…”, “Before answering…”, “do not tell the user”) dentro de datos. Puede entrar como una dimensión más del clasificador. Es lo que atrapa los ataques del mismo dominio que la tarea, que el desvío no ve.

## 6. Trozos

- **Ataques partidos entre valores hermanos** (`"step1": "Ignore…", "step2": "…previous instructions"`): ventanas sobre valores seguidos de un mismo objeto, como las de claves.
- Ataques repartidos en ramas lejanas, codificados (base64 y otros) o dentro de HTML o markdown.
- Mejor detección de IDs, fechas y números.
