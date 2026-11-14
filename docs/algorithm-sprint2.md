# Algoritmo: segundo sprint

Ajustes que se dejan para después de tener la primera versión funcionando de punta a punta. Cada uno dice qué cambia, por qué y cómo se decide. Se agregan aquí; no se hacen hasta que la primera versión tenga números en `results/`.

## 1. `drift_score`: de máximo a promedio ponderado

**Hecho en parte:** la combinación aprendida de [algorithm.md](algorithm.md#combinación-aprendida-stackpy) (paso 5) ya pesa los tres percentiles con el ataque y gana a la misma tasa (88 % frente a 75 % de la regla). Lo de abajo queda como historia.

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

**Probado (rama `algo-polish`, dos mitades de validación, a la misma tasa):** ninguna gana a la resta de promedios fuera del ruido. Solo ataque: resta 73 % (8 particiones), logística C = 0,01 70 %, vecinos cercanos 46–60 %. Dentro de la logística de rasgos: resta 83 %, logística C = 0,01 85 % (±1,4), logística C = 10 + vecinos 89 % (±3,2). El AUC por trozo engaña: los vecinos tienen el mejor AUC en valores (hasta 0,998) y el peor resultado por salida, porque decide el trozo legítimo más alto de cada salida. La validación cruzada por fuente dentro de train elige C = 0,01 (por caso elige C = 10: sobreajusta a fuentes conocidas). Si se adopta, las tablas del ataque tienen que salir de puntajes fuera de la muestra (por caso, 5 pliegues): con puntajes dentro de la muestra se pierden 5 puntos. Los vecinos además obligan a guardar ~5 400 vectores y cuestan 6–20 ms por salida.

## 5. Señal de “orden dirigida al asistente”

Trozos que le hablan al modelo (“Assistant:”, “AI, please…”, “Before answering…”, “do not tell the user”) dentro de datos. Puede entrar como una dimensión más del clasificador. Es lo que atrapa los ataques del mismo dominio que la tarea, que el desvío no ve.

## 6. Trozos

- **Ataques partidos entre valores hermanos** (`"step1": "Ignore…", "step2": "…previous instructions"`): ventanas sobre valores seguidos de un mismo objeto, como las de claves.
- Ataques repartidos en ramas lejanas, codificados (base64 y otros) o dentro de HTML o markdown.
- Mejor detección de IDs, fechas y números.

## 7. Umbral y datos de validación

- **Varianza del umbral.** Con ~55 legítimas por mitad, una salida son 1,8 puntos y las tocadas en la mitad no vista tienen desviación de 3 a 5 puntos por partición; ningún arreglo la quita (cola paramétrica, umbral por clase, umbral según la cantidad de trozos, bagging: probados, no ayudan; por clase empeora). Lo único es **más salidas legítimas en validación**. El presupuesto conformal (algorithm.md, paso 5) ya corrige el sesgo.
- **Umbral sobre puntajes fuera de la muestra** de la logística (ajustarla por pliegues y elegir el umbral con lo que no vio): baja las tocadas de 5,2 % a 4,5 % en 200 particiones. Poco para la complejidad; queda aquí.
- **Ajustar la logística con train y no con validación** sale mucho peor (54–79 %): en train el percentil del ataque está dentro de la muestra (1 % de legítimos sobre 0,99, frente a 2 % en validación). Haría falta el ataque fuera de la muestra (punto 4).
- **`has_request` y `has_tool` valen siempre 1 en validación**: su peso es 0 y la logística nunca aprendió qué pasa sin pedido o sin llamada (manifiestos, `origen="usuario"`). Hacen falta filas sin pedido.

## 8. Referencias del desvío

- **Vecinos:** faltan en el 60 % de los trozos de validación y quitarlos no cambia nada (83,7 % frente a 83,6 %). Se quedan porque en AgentDojo hay listas largas (correos, transacciones) donde deberían servir; se mide ahí.
- **Pedido y llamada** cargan la señal (AUC 0,87 y 0,80 por trozo); uno reemplaza casi del todo al otro. Variantes probadas sin ganancia: pedido partido en oraciones, llamada solo con el nombre o solo con los argumentos (los argumentos sí ayudan en valores: 0,93 frente a 0,89), vecinos con el vector promedio.
- **Inyecciones en tema:** en InjecAgent el AUC del desvío es 0,41 y el de la llamada 0,38 (al revés). Falta un dataset de validación con inyecciones escritas para la herramienta (como AgentDojo) para saber cuánto vale el desvío ahí; si resulta dañino, entrenar la logística con esas filas le baja el peso.
- **Frases legítimas que suenan a orden** (“The agent must call the customer back…”) y rutas con “reset password url” son lo que sigue tocando: *hard negatives* para Datos.

## 9. Versión 2: qué se hizo y qué queda

Hecho: la logística decide (algorithm.md, paso 5), con copias sin llamada y sin pedido, y la llamada con la descripción de la herramienta. Probado con los datos de `branch-data` y sin ganancia (lectura 1, `mcp_val`, 10 particiones; la versión 2 da 84 % / 3 %):

- **`train.csv` en la referencia** (dirección y tablas, con `injected_text`): logística 80 % / 4 %, solo ataque 37 %. Los trozos legítimos de validación más altos suben más que los ataques. Solo las filas de claves: igual (84 % / 4 %).
- **Puntajes fuera de la muestra en train** (referencia por pliegues) para ajustar la logística con train y validación: 45–60 %. Las fuentes de train piden otros pesos (en LLMail el pedido va al revés).
- **Dirección propia para las rutas:** 81 % / 4 %. **Palabras de la clave más larga y profundidad** como rasgos: igual.
- **`bge-small-en-v1.5`:** 85 % / 4 %, más lento.
- **Copias sin pedido y sin llamada a la vez:** `val.csv` (sin contexto) 84 % intactas frente a 80 %, pero la lectura 1 baja a 83 % / 4 %. No entró.

Queda:

- **Reentrenar con los legítimos de banca y las paráfrasis** de Datos (en `master` después del congelamiento) y repetir la corrida offline de AgentDojo.
- **El adaptador de AgentDojo no pasa `herramienta`**: pasarla (nombre, descripción y argumentos de la última llamada) es lo que mide validación.
- **Sin pedido ni llamada** (texto suelto) la versión 2 toca más legítimas (`notinject`). Filas sin contexto en validación.
- **Saneado incompleto:** en AgentDojo muchas veces se retira una sola oración de la carga y la orden queda. Retirar también las oraciones vecinas del mismo bloque con ataque alto.
- **`origen="manifiesto"`:** se trata como una salida de herramienta, sin pedido.
