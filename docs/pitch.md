# Ficha técnica, resumen y pitch

Dueño: **Pitch**. No hay diapositivas: en los 3 minutos se proyecta la ficha técnica y el jurado la lee mientras hablamos. La ficha es, a la vez, la diapositiva, el informe y lo que el jurado vuelve a mirar al calificar.

## Checklist de entrega

- [ ] Registro del equipo antes de las **11:00** (`/defacchackathon/registro`, Track 1).
- [ ] Plantilla oficial de la ficha pedida a la organización en la primera hora.
- [ ] Ficha en PDF, máximo 2 páginas y 10 MB, con números de `results/`.
- [ ] Resumen de 150 a 250 palabras.
- [ ] Repo con README reproducible, `results/` y `CITATIONS.md` completo.
- [ ] Video corto de la demo (`bench/demo.py`), enlazado en la ficha y el README.
- [ ] Entrega en `/defacchackathon/entregar` a las **16:00** (cierre estricto 17:00).

## La ficha, página por página

**Página 1 · qué y por qué (se lee en 1 minuto)**
1. Título y una frase: “Un guardián de milisegundos que retira las instrucciones escondidas en las salidas de las herramientas antes de que lleguen al LLM.”
2. Vector de amenaza: un ejemplo real de AgentDojo: la tarea inocente, la salida de la herramienta con la inyección resaltada y lo que el agente hace sin defensa.
3. Defensa: el diagrama simplificado (herramienta → guardián → contexto) y los dos puntajes.
4. La demo en una captura: salida cruda contra salida limpia.

**Página 2 · la evidencia (se lee en 1 minuto)**
1. Metodología en 4 líneas: AgentDojo (suite, modelo, n), líneas base, conjunto propio del detector, regla de no fuga.
2. Resultados: una tabla (sin defensa, palabras clave, DeBERTa, `guard-detect`, `guard-sanitize`) con utilidad, utilidad bajo ataque, éxito del ataque y latencia; los tres números clave en grande arriba.
3. Limitaciones y riesgo de uso dual ([idea.md](idea.md)).
4. Reproducción y citas: el comando, el commit y `CITATIONS.md`.

## Borrador del resumen (completar los números)

> Los agentes con herramientas pueden ser secuestrados por instrucciones escondidas en lo que leen: un correo, un documento o la respuesta de un servidor MCP (inyección indirecta). Presentamos un guardián de contexto que revisa cada salida de herramienta antes de que entre a la ventana de contexto del LLM. La salida se parte en trozos y cada trozo se compara, con embeddings, contra una dirección de “instrucción maliciosa” aprendida de datos públicos y sintéticos y contra la tarea que pidió el usuario. Los trozos sospechosos se retiran y el agente sigue con el resto, en vez de descartar toda la salida como hacen los detectores existentes. Es determinista, no gasta tokens y tarda __ ms. En AgentDojo (suite __, __ casos, modelo __), redujo el éxito de los ataques de __ % sin defensa a __ %, conservando __ % de utilidad bajo ataque, frente a __ % del detector DeBERTa y __ % de un filtro de palabras clave. Ningún texto de AgentDojo se usó para entrenar ni para elegir umbrales. Límites: un atacante que conozca el guardián puede reescribir sus ataques, la evaluación es en inglés y con un solo modelo, y los umbrales dependen del dominio. Publicamos el método defensivo, no un servicio de puntajes. Código, datos y resultados se reproducen con un comando.

## Guion de 3 minutos

| Tiempo | En la ficha | Qué se dice |
|---|---|---|
| 0:00–0:25 | ejemplo de la amenaza | “El usuario pidió pagar una factura. La factura traía escondida otra orden: transferir el dinero a otra cuenta. El usuario no hizo nada malo.” |
| 0:25–1:00 | vector de amenaza | Qué es la inyección indirecta y por qué es el riesgo del Track 1: los agentes tratan lo que leen como órdenes. |
| 1:00–1:40 | diagrama de la defensa | La idea del mapa en una frase; sanear en vez de bloquear; milisegundos y cero tokens. |
| 1:40–2:30 | tabla de resultados | Éxito del ataque y utilidad, contra sin defensa, palabras clave y DeBERTa. Siempre los dos números juntos. |
| 2:30–3:00 | límites y uso dual | La limitación principal y el cierre: “Su agente puede seguir leyendo el mundo sin obedecerlo.” |

## Preguntas probables (respuestas de 20 segundos)

- **¿Y un atacante que reescribe el ataque hasta que pase?** Es la limitación principal; lo medimos con paráfrasis y lo decimos en la ficha. Es una capa barata delante de otras, no la defensa completa.
- **¿Por qué embeddings y no un LLM que juzgue?** Un juez cuesta tokens, tarda segundos y también puede ser inyectado. El nuestro es determinista, de milisegundos y explica qué retiró.
- **¿Cuánto daña las tareas normales?** Medimos utilidad con y sin ataque contra las mismas líneas base.
- **¿Entrenaron con AgentDojo?** No: ningún texto de AgentDojo entra al entrenamiento ni a los umbrales.
- **¿Cómo lo reproduzco?** Un comando del README regenera la tabla de la ficha.
