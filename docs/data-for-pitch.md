# Datos para la ficha y el pitch

**Para:** Pitch. **De:** Datos. **Fecha:** 2026-11-14.

Todos los números salen de `data/QUALITY.md`, que se genera con `python data/build.py`. Ninguno se eligió a mano. Si se regeneran los datos, hay que volver a copiarlos de ahí.

## Para la ficha (página 2, "Metodología")

> Conjunto propio de **3.542 salidas de herramienta**, la mitad ataques y la mitad legítimas (1.771 y 1.771). Viene de 4 datasets públicos (LLMail-Inject, InjecAgent, Glaive, NotInject) y de salidas sintéticas que imitan correos, chats, tickets, páginas web y JSON de APIs. Se divide **por fuente**: el test (1.434 filas) tiene fuentes y estilos que no aparecen en el entrenamiento, como los ataques humanos de la fase 2 de LLMail, reseñas, páginas web y respuestas de API. **Ningún texto de AgentDojo** entra al conjunto y **ningún texto se repite** entre train, val y test. El 35 % de las salidas estructuradas va en YAML, con la misma función que usa AgentDojo.

## Números que pueden ir en grande

- **3.542** salidas etiquetadas (de 4.911 candidatas; el resto se descartó por duplicados, idioma o desequilibrio).
- **696 legítimos difíciles (hard negatives):** textos inofensivos que dicen "ignore", "urgent" u "override" para que el detector no aprenda palabras sueltas.
- **1.054 casos MCP completos:** prompt del usuario, descripción de la herramienta y respuesta JSON-RPC, listos para la demo.
- **0** textos de AgentDojo, **0** textos repetidos entre splits y **0** datos de atacante (correos, URL, IBAN) compartidos entre splits.

| Split | Filas | Ataques | Legítimos | Hard negatives |
|---|---|---|---|---|
| train | 1.628 | 814 | 814 | 258 |
| val | 480 | 240 | 240 | 120 |
| test | 1.434 | 717 | 717 | 318 |

## Respuestas para el jurado

- **¿De dónde salen los datos?** De datasets públicos con licencia MIT o Apache-2.0 más sintéticos propios. Todo está citado en `CITATIONS.md`, y los datos del atacante son ficticios.
- **¿El detector no memoriza el estilo del dataset?** El test usa fuentes distintas a las de entrenamiento. Además medimos los atajos posibles, como la longitud o la presencia de URL (ver "Limitaciones").
- **¿Y los manifiestos MCP (descripciones de herramientas envenenadas)?** Hay un conjunto aparte de 956 descripciones, de MCPTox y ToolACE. Es solo para evaluar y no se publica, porque MCPTox no declara licencia.

## Limitaciones (para la sección de límites)

- Todo está en inglés, como AgentDojo.
- **Los ataques suelen ser más largos y traen más URL o correos** que los legítimos: 70–83 % de los ataques frente a 14–25 % de los legítimos. Un detector podría apoyarse en eso, así que lo medimos y lo reportamos.
- Hay pocos ataques "difíciles": paráfrasis sin palabras de alerta, base64, HTML o instrucciones repartidas en varios campos.

## Avisos

1. En [pitch.md](pitch.md) la respuesta sobre el atacante que reescribe dice "**lo medimos con paráfrasis**", pero **ese conjunto todavía no existe**. O Datos lo construye antes de la entrega, o hay que cambiar la frase a "es la limitación principal".
2. **Los resultados del guardián** (éxito del ataque, utilidad, latencia, AUC) **no salen de Datos**: los produce Integración en `results/`. Este documento describe solo los datos.
