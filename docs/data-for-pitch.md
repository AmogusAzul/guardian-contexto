# Datos para la ficha y el pitch

**Para:** Pitch. **De:** Datos. **Fecha:** 2026-11-14.

Todos los números salen de `data/QUALITY.md`, que se genera con `python data/build.py`. Ninguno se eligió a mano. Si se regeneran los datos, hay que volver a copiarlos de ahí.

## Para la ficha (página 2, "Metodología")

> Conjunto propio de **3.878 salidas de herramienta**, la mitad ataques y la mitad legítimas (1.939 y 1.939). Viene de 4 datasets públicos (LLMail-Inject, InjecAgent, Glaive, NotInject) y de salidas sintéticas que imitan correos, chats, tickets, páginas web, JSON de APIs y pagos bancarios. Se divide **por fuente**: el test (1.562 filas) tiene fuentes y estilos que no aparecen en el entrenamiento, como los ataques humanos de la fase 2 de LLMail, reseñas, páginas web y respuestas de API. **Ningún texto de AgentDojo** entra al conjunto y **ningún texto se repite** entre train, val y test. El 35 % de las salidas estructuradas va en YAML, con la misma función que usa AgentDojo.

## Números que pueden ir en grande

- **3.878** salidas etiquetadas (de 5.259 candidatas; el resto se descartó por duplicados, idioma o desequilibrio).
- **884 legítimos difíciles (hard negatives):** textos inofensivos que dicen "ignore", "urgent" u "override", o que hablan de pagos e IBAN, para que el detector no aprenda palabras ni temas sueltos.
- **1.174 casos MCP completos:** prompt del usuario, descripción de la herramienta y respuesta JSON-RPC, listos para la demo.
- **0** textos de AgentDojo, **0** textos repetidos entre splits y **0** datos de atacante (correos, URL, IBAN) compartidos entre splits.

| Split | Filas | Ataques | Legítimos | Hard negatives |
|---|---|---|---|---|
| train | 1.784 | 892 | 892 | 336 |
| val | 532 | 266 | 266 | 166 |
| test | 1.562 | 781 | 781 | 382 |

## Respuestas para el jurado

- **¿De dónde salen los datos?** De datasets públicos con licencia MIT o Apache-2.0 más sintéticos propios. Todo está citado en `CITATIONS.md`, y los datos del atacante son ficticios.
- **¿El detector no memoriza el estilo del dataset?** El test usa fuentes distintas a las de entrenamiento. Además medimos los atajos posibles, como la longitud o la presencia de URL (ver "Limitaciones").
- **¿No marca como ataque cualquier pago?** Ese sesgo existía (los textos con IBAN eran 74–100 % ataques) y se corrigió con legítimos de banca: ahora son 46–54 %. Se agregaron después de una corrida de prueba en AgentDojo `banking`, sin copiar textos de AgentDojo (`docs/data-banking-negatives.md`).
- **¿Y los manifiestos MCP (descripciones de herramientas envenenadas)?** Hay un conjunto aparte de 956 descripciones, de MCPTox y ToolACE. Es solo para evaluar y no se publica, porque MCPTox no declara licencia.

## Limitaciones (para la sección de límites)

- Todo está en inglés, como AgentDojo.
- **Los ataques suelen ser más largos y traen más URL o correos** que los legítimos: 62–81 % de los ataques frente a 13–21 % de los legítimos. Un detector podría apoyarse en eso, así que lo medimos y lo reportamos.
- Las paráfrasis (`data/paraphrase.csv`) son reescrituras a mano, no un atacante que optimiza contra el guardián. Faltan ataques en base64, HTML o repartidos en varios campos.

## Avisos

1. **Ya existe el conjunto de paráfrasis** (`data/paraphrase.csv`), así que la respuesta de [pitch.md](pitch.md) "lo medimos con paráfrasis" puede quedar, **cuando Integración corra el guardián sobre él**. Son 216 ataques en tres versiones emparejadas (literal, reescritura leve y reescritura **sin palabras de alerta**) y 120 legítimos con la misma forma. El número para la ficha es la detección por versión: "detecta X % de los ataques literales y Y % de los reescritos sin palabras de alerta, frente a Z % del filtro de palabras clave".
2. **Los resultados del guardián** (éxito del ataque, utilidad, latencia, AUC) **no salen de Datos**: los produce Integración en `results/`. Este documento describe solo los datos.
