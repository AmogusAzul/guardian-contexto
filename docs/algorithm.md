# El algoritmo

Dueño: **Algoritmo**. Código en `guard/`. Contrato en [architecture.md](architecture.md#contrato-1-check).

## Versión 1 (la que se construye primero)

1. **Trozos:** separar la salida de la herramienta en oraciones; ventanas de 1 a 3 oraciones que se solapan, más el texto completo si es corto. Ignorar trozos de menos de 4 palabras.
2. **Embeddings:** un modelo pequeño de `sentence-transformers` en CPU (por ejemplo `BAAI/bge-small-en-v1.5` o `all-MiniLM-L6-v2`; AgentDojo está en inglés). Normalizar los vectores. Alternativa si el CPU no alcanza: `text-embedding-3-small` de OpenAI (cuesta tokens y red; anotarlo).
3. **Centrar:** restar el embedding promedio del corpus de entrenamiento y volver a normalizar (los embeddings viven en un “cono” estrecho y casi todos los cosenos se parecen).
4. **`attack_score`:** coseno de cada trozo con la dirección de ataque = promedio(inyecciones) − promedio(legítimos). Reescalar a 0–1 con los percentiles de validación.
5. **`drift_score`:** 1 − coseno entre el trozo y la tarea del usuario (el primer mensaje del usuario en la conversación). Sin tarea, `None`.
6. **Decisión por trozo:** marcar si `attack_score ≥ τ_alto`, o si `attack_score ≥ τ_bajo` y `drift_score ≥ τ_drift`. Los tres umbrales se eligen en validación (ver [evaluation.md](evaluation.md)).
7. **Saneo:** reemplazar los trozos marcados (unidos si se solapan) por `[contenido retirado por el guardián]`.

## Versión 2 (si la 1 funciona y hay tiempo, en orden)

1. **Regresión logística** sobre los embeddings en vez de la resta de promedios: el mismo tipo de modelo (un vector de pesos y un umbral), mejor dirección.
2. **Vecinos cercanos:** `attack_score` = similitud con la inyección más cercana − similitud con el legítimo más cercano. Los *hard negatives* hacen de contrapeso y la explicación sale gratis (“se parece a este ataque conocido”).
3. **Señal de “orden dirigida al asistente”:** trozos que le hablan al modelo (“Assistant:”, “AI, please…”, “Before answering…”) dentro de datos. Puede entrar como una dimensión más del clasificador.

## Por qué podría fallar (y qué se ve)

| Problema | Síntoma | Arreglo |
|---|---|---|
| Las inyecciones no son un solo grupo (rol, exfiltración, “importante”, ofuscadas) | Detecta un estilo y no otro | Regresión logística o vecinos cercanos |
| Los embeddings miden tema, no intención | Falsos positivos en correos que dan órdenes normales (“please send the report by Friday”) | *Hard negatives* en entrenamiento; señal de `drift_score` |
| Atajo del dataset: las inyecciones de entrenamiento tienen otro estilo que los textos legítimos | Números excelentes en validación y malos en AgentDojo | Inyecciones escritas como salidas de herramienta; separar por fuente |
| Anisotropía | Umbrales inestables | Centrar (paso 3) |
| Trozos cortos o ataques partidos | Falsos positivos en textos largos; ataques que pasan | Ventanas que se solapan; umbral calibrado por trozo |
| Atacante adaptativo | Paráfrasis que pasan | Se reconoce como límite; conjunto de paráfrasis en la evaluación |

## Regla de oro contra la fuga de datos

**Ningún texto de AgentDojo entra al entrenamiento ni a la elección de umbrales.** AgentDojo es el examen final. El entrenamiento usa otras fuentes ([evaluation.md](evaluation.md#datos)).
