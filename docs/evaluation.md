# Evaluación

La rúbrica da 5 en Ejecución a lo que “funciona de punta a punta, se puede reproducir y se evaluó contra una línea base”. Todo número de la ficha sale de `results/` y se reproduce con un comando del README.

## La frase que queremos poder decir

> “En AgentDojo (`<suite>`, `<modelo>`, n = __ casos), el guardián bajó el éxito de los ataques de __ % a __ % conservando __ % de utilidad bajo ataque, frente a __ % del detector DeBERTa, y tarda __ ms por salida.”

## Benchmarks

### Principal: AgentDojo (con la clave de OpenAI)

- Agentes reales con herramientas en entornos simulados (`banking`, `workspace`, `slack`, `travel`) e inyecciones indirectas en las salidas de las herramientas. Licencia MIT.
- Instalar: `pip install agentdojo` (y `pip install "agentdojo[transformers]"` para el detector DeBERTa).
- Ejemplo de corrida: `python -m agentdojo.scripts.benchmark -s banking -ut user_task_0 -ut user_task_1 --model <modelo> --defense transformers_pi_detector --attack important_instructions` (opciones exactas: verificar con `--help` en el bloque 1).
- **Modelo:** el más barato de OpenAI que use herramientas bien (por ejemplo `gpt-4o-mini`, si sigue disponible). Todas las defensas se corren con el **mismo** modelo: la tabla publicada usa `gpt-4o-2024-05-13` y no es comparable directamente.
- **Costo:** primero 2 tareas de usuario × 2 inyecciones para medir tokens por caso; luego una suite completa (`banking` primero, la más parecida a “reembolsos y pagos”). Poner un límite de gasto en la cuenta de OpenAI.

### Secundario: nivel detector (sin API)

Conjunto de prueba propio (`data/test.csv`): trozos de salidas de herramientas, inyectados y legítimos, de fuentes que no se usaron para entrenar. Mide el guardián solo, rápido y gratis.

### Si alcanza: MCPTox

Unas 160 descripciones de herramientas MCP envenenadas (sin licencia declarada: se usan solo como datos y se citan). Se pasan por `check(..., origen="manifiesto")`. Solo trae casos maliciosos: Datos arma descripciones limpias de servidores MCP públicos para medir falsos positivos.

## Datos

- **Entrenamiento y validación:** inyecciones escritas como salidas de herramienta (correos, documentos, respuestas de API), sintéticas o de datasets públicos de inyección (por ejemplo `deepset/prompt-injections`; verificar licencia), más salidas legítimas y *hard negatives*. Separar **por fuente o plantilla**, no al azar; quitar casi-duplicados (coseno > 0,95) antes.
- **Prueba:** fuentes distintas. **Ningún texto de AgentDojo** en entrenamiento ni en la elección de umbrales.
- **Robustez (opcional, ~20 cada uno):** paráfrasis de las inyecciones de prueba, ofuscadas (errores, espacios raros), escondidas en textos largos.

## Métricas

| Nivel | Métrica | Qué queremos |
|---|---|---|
| AgentDojo | Utilidad (sin ataque) | casi igual que sin defensa |
| AgentDojo | Utilidad bajo ataque | más alta que DeBERTa |
| AgentDojo | Éxito del ataque (targeted ASR) | mucho más bajo que sin defensa |
| Detector | Detección por trozo / falsos positivos | detección alta con falsos positivos ≤ 5 % |
| Ambos | Latencia de `check()` (mediana, p95) | < 300 ms |
| AgentDojo | Tokens por caso | reportar; el guardián no gasta tokens |

Reglas: siempre con su `n` e intervalo de confianza (Wilson); detección junto a falsos positivos, y éxito del ataque junto a utilidad; por categoría además del total.

## Líneas base (todas con el mismo modelo y tareas)

1. **Sin defensa.**
2. **Filtro de palabras clave** (implementado como otro `PromptInjectionDetector`): la línea base obligatoria, “lo que cualquiera haría en una tarde”.
3. **Detector DeBERTa** de AgentDojo (`transformers_pi_detector`): el rival directo.
4. Opcional: `tool_filter` o `spotlighting_with_delimiting`, ya incluidas en AgentDojo.

Nuestras dos variantes: `guard-detect` (descarta la salida, como DeBERTa) y `guard-sanitize` (retira solo los trozos). Si `guard-sanitize` conserva más utilidad que `guard-detect` con un éxito del ataque parecido, esa es la tesis demostrada.

Referencia publicada (gpt-4o-2024-05-13, ataque `important_instructions`, de la tabla de AgentDojo; verificar en <https://agentdojo.spylab.ai> antes de citar):

| Defensa | Utilidad | Utilidad bajo ataque | Éxito del ataque |
|---|---|---|---|
| Ninguna | 69,1 % | 50,1 % | 47,7 % |
| `tool_filter` | 72,2 % | 56,3 % | 6,8 % |
| `spotlighting_with_delimiting` | 72,2 % | 55,6 % | 41,7 % |
| `repeat_user_prompt` | 84,5 % | 67,3 % | 27,8 % |
| Detector DeBERTa | 41,2 % | 21,1 % | 8,0 % |

## Procedimiento

1. Construir el guardián solo con entrenamiento.
2. Elegir los umbrales en validación: los más bajos que dejen los falsos positivos en 5 % o menos.
3. Congelar (modelo, umbrales, trozos) y anotar el commit.
4. Correr el conjunto de prueba del detector y AgentDojo **una sola vez** con todas las defensas. Si después se cambia algo, se dice en la ficha.
5. Guardar todo en `results/` (Contrato 4). El README trae el comando exacto.

## Demo para la ficha y el video

`bench/demo.py`: toma un caso real de AgentDojo con inyección y muestra lado a lado la salida cruda de la herramienta, la salida limpia (con el trozo retirado resaltado y sus puntajes) y qué hizo el agente con y sin guardián. Esas capturas van a la ficha.
