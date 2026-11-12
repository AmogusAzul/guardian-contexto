# Por qué el algoritmo podría no funcionar, y cómo hacer que funcione

Complemento del [plan de arranque](one-page-plan.md). Lo lee sobre todo el rol **Algoritmo**, pero el rol **Datos** debe leer la sección "Datos" y el rol **Pitch** la sección "Qué decir en el pitch".

## El pipeline actual (versión ingenua)

1. Calcular el embedding de cada fila del dataset.
2. **Vector de ataque** = promedio de embeddings `attack` − promedio de embeddings `benign`.
3. **Vector de tema** = promedio de embeddings de los documentos del RAG.
4. Partir el mensaje en trozos; `attack_score` = coseno máximo entre un trozo y el vector de ataque; `topic_score` = coseno entre el mensaje y el vector de tema.
5. Dos umbrales fijos deciden `allow`, `block_attack` o `block_off_topic`.

## Por qué podría fallar

| # | Problema | Qué se ve en la demo |
|---|---|---|
| 1 | **Los ataques no son un solo grupo.** Jailbreak por juego de rol, robo del prompt de sistema, instrucciones escondidas, texto ofuscado (base64, leetspeak), otros idiomas. El promedio de grupos distintos puede quedar lejos de todos. | Detecta "ignora tus instrucciones" pero deja pasar un jailbreak de rol. |
| 2 | **Los embeddings miden tema, no intención.** "Ignora las instrucciones anteriores" y "¿Cómo ignoro los warnings en Python?" se parecen mucho para un modelo de embeddings genérico. | Falsos positivos justo en los *hard negatives*. |
| 3 | **El atajo del dataset.** Los datasets públicos de ataques están casi todos en inglés y nuestros benignos en español; la resta de promedios aprende "inglés vs. español" (o "largo vs. corto"), no "ataque vs. normal". | Números excelentes en la evaluación y fallos en vivo con ataques en español. |
| 4 | **Anisotropía.** Los embeddings viven en un "cono" estrecho: casi todos los cosenos caen entre 0,6 y 0,9 y la señal útil es una diferencia pequeña. | Umbrales que cambian muchísimo con cada dato nuevo. |
| 5 | **Trozos (chunks).** Trozos cortos dan embeddings ruidosos; tomar el máximo sobre muchos trozos sube los falsos positivos en mensajes largos; un ataque partido en dos trozos se diluye. | Mensajes largos y normales bloqueados; ataques largos que pasan. |
| 6 | **Un solo vector de tema.** "Hola", "gracias" o "¿y eso por qué?" no se parecen al promedio de los documentos del curso. | El chatbot bloquea saludos y preguntas de seguimiento. |
| 7 | **Ataque envuelto en el tema.** "Para mi tarea de Java, ignora tus reglas y…" sube el `topic_score` y diluye el `attack_score`. | Un jurado lo prueba y pasa. |
| 8 | **Pocos datos de evaluación.** Con ~50 ataques de prueba, cada error mueve la detección 2 puntos; elegir el umbral sobre los mismos datos infla los resultados. | Diapositiva con números que no se sostienen si preguntan. |
| 9 | **Solo miramos lo que escribe el usuario.** Una inyección dentro de un documento del RAG o de la salida de una herramienta (inyección indirecta) nunca pasa por `check()`. | Limitación de alcance: hay que decirla, no esconderla. |

## Cómo hacer que funcione (en orden de costo)

1. **Modelo multilingüe y local.** Usar un modelo de embeddings multilingüe que corra en CPU, p. ej. `intfloat/multilingual-e5-small` o `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Es determinista, rápido (<50 ms por mensaje corto) y no gasta tokens. Arregla parte de (3).
2. **Datos sin atajos (rol Datos).** Mismos idiomas en ambas clases: traducir ~50 ataques al español y escribir benignos también en inglés. Longitudes parecidas. ≥30 *hard negatives*. Quitar casi-duplicados (coseno > 0,95) **antes** de separar los conjuntos. Separar train/validación/test **por fuente o plantilla**, no al azar, para que la misma plantilla de ataque no esté en los dos lados. Arregla (3) y (8).
3. **Centrar los embeddings.** Restar el embedding promedio de todo el corpus y volver a normalizar antes de calcular cosenos. Barato y arregla gran parte de (4).
4. **De un vector a un clasificador lineal.** La resta de promedios ya es un clasificador lineal; una **regresión logística** sobre los embeddings encuentra la mejor dirección con los mismos datos. Sigue siendo "pseudo-determinista": un vector de pesos y un umbral fijo. Comparar los dos en validación. Arregla parte de (1) y (2).
5. **Varios prototipos + vecinos cercanos.** Agrupar los ataques en k ≈ 5–10 centroides (k-means) o usar k vecinos más cercanos sobre el dataset etiquetado. `attack_score` = similitud al ataque más cercano − similitud al benigno más cercano. Los *hard negatives* actúan como contrapeso: "cómo mato un proceso" queda más cerca de su gemelo benigno que de cualquier ataque. Arregla (1) y (2), y además da una explicación gratis para la demo ("se parece a este ataque conocido").
6. **Tema por vecino más cercano.** `topic_score` = similitud máxima con los **trozos** del RAG, no con su promedio. Añadir una clase pequeña de mensajes conversacionales ("hola", "gracias", "explícalo de nuevo") que siempre pasan, y calcular el tema con el mensaje anterior incluido. Arregla (6).
7. **Trozos bien hechos.** Ventanas de 1–3 oraciones que se solapan **más** el mensaje completo; calibrar el umbral de trozo por separado del de mensaje completo; ignorar trozos de menos de ~4 palabras. Arregla (5) y parte de (7): el trozo "ignora tus reglas" se evalúa solo, sin el envoltorio del tema.
8. **Umbrales con presupuesto de falsos positivos.** Elegir el umbral en **validación** para que como máximo ~5 % de las preguntas legítimas se bloqueen, y reportar la detección a ese umbral en **test**. Mostrar la curva ROC y el intervalo de confianza. Arregla (8).
9. **Zona gris.** Con dos umbrales por puntaje: claro → decisión inmediata; dudoso → (si hay tiempo) un juez LLM barato o simplemente `allow` con advertencia en el panel. El filtro de embeddings es la **primera capa**, rápida y barata, no la defensa completa.
10. **Si sobra tiempo:** pasar también por `check()` los trozos del RAG que se le mandan al LLM (inyección indirecta, problema 9).

## Plan mínimo para la hackathon

- **CP1:** mock conectado de punta a punta (sin algoritmo real).
- **CP2:** embeddings multilingües + vector ingenuo (pasos 1–3) sobre las primeras filas; `eval.py` ya imprime números, aunque sean malos.
- **CP3:** comparar en validación: vector ingenuo vs. regresión logística vs. vecinos cercanos (pasos 4–5); quedarse con el mejor. Arreglar tema (paso 6).
- **CP4:** fijar umbrales (paso 8), congelar el modelo, correr test **una sola vez** y pasarle los números a Pitch.

## Qué decir en el pitch

- "Es una primera capa: determinista, barata (sin tokens) y explicable ('se parece a este ataque conocido')."
- Comparar contra el filtro de palabras clave **en el mismo conjunto de test**, con el mismo presupuesto de falsos positivos.
- Nombrar las limitaciones sin que pregunten: ataques adaptativos (paráfrasis), inyección indirecta, tamaño del dataset.
