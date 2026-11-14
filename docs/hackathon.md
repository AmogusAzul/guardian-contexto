# La hackathon: reto, rúbrica, entregables y reglas

Hechos del evento que condicionan el proyecto. Fuentes (leídas el 2026-11-13): <https://www.aisafetycolombia.org/defacchackathon> (y sus páginas `/guia`, `/entregar`, `/registro`). Si algo aquí contradice a la organización, gana la organización.

## Reto

- 8 horas de trabajo continuo: **sábado 14 de noviembre de 2026, 9:00 a 17:00**.
- Construir y evaluar un prototipo defensivo (enfoque def/acc: defensas que favorezcan a quien defiende).
- Toda entrega responde cuatro preguntas: (1) el vector de riesgo, (2) el mecanismo defensivo, (3) la validación empírica (benchmarks, tasa de detección, falsos positivos), (4) limitaciones y riesgo de uso dual.

## Nuestro track: Track 1, seguridad de agentes

- **Resumen oficial:** cuando los sistemas de IA ejecutan acciones con herramientas reales (archivos, navegadores, terminales, servidores MCP), una instrucción oculta en un documento o una web puede secuestrar al agente (inyección indirecta) para exfiltrar información o ejecutar comandos no autorizados.
- **Para empezar:** un auditor o filtro que inspeccione manifiestos y llamadas a herramientas MCP, evaluado en **MCPTox**.
- **Con experiencia:** una arquitectura defensiva medida en **AgentDojo** o AgentDyn: cuántos ataques neutraliza sin degradar las tareas legítimas.
- Recursos oficiales: AgentDojo (<https://github.com/ethz-spylab/agentdojo>), MCPTox (<https://github.com/zhiqiangwang4/MCPTox-Benchmark>), AgentDyn (<https://github.com/SaFo-Lab/AgentDyn>).

## Rúbrica

Al menos 2 jurados por proyecto. Tres criterios de 1 a 5, mismo peso (máximo 15). **Empate: gana el de mayor Impacto.**

| Criterio | 5 = excepcional |
|---|---|
| Impacto potencial e innovación | Riesgo importante y poco atendido; enfoque original con ventaja clara que un equipo real podría adoptar. |
| Calidad de ejecución | Funciona de punta a punta y se puede reproducir; **evaluado contra una línea base**; analiza límites y riesgo de uso dual. |
| Presentación y claridad | Un jurado lo entiende en 2 minutos; ficha concisa con los resultados clave. |

Un 3 es “trabajo sólido para un día”. **Un proyecto que principalmente facilita ataques, sin mitigación, no es elegible para premio.**

## Fechas y entregables

| Hora | Qué |
|---|---|
| 9:00 | Empieza el trabajo |
| **11:00** | Cierra el registro del equipo (una persona, en `/defacchackathon/registro`: nombre, integrantes, track) |
| 14:00 | Se publica el orden de los pitches |
| **16:00** | Entrega sugerida en `/defacchackathon/entregar` |
| **17:00** | Cierre estricto de entregas |
| 17:10 | Pitches de **3 minutos**, sin diapositivas: se proyecta la **ficha técnica** |

Entrega única: nombre del equipo, integrantes (2 a 5, con el correo con que aplicaron), título, track, **resumen de 150 a 250 palabras**, enlace al repo (ejecutable, código documentado) o demo, y **ficha técnica en PDF** (máximo 2 páginas, 10 MB). La plantilla oficial de la ficha no está publicada: hay que pedirla (correcciones y preguntas: `equipo@aisafetycolombia.org`). Campos que debe cubrir: vector de amenaza, arquitectura defensiva, metodología de evaluación, resultados cuantitativos, límites y riesgo dual.

## Reglas que afectan el trabajo

- Prohibido atacar o escanear sistemas reales de terceros (Ley 1273 de 2009). Todo en laboratorio, benchmarks públicos o datos sintéticos.
- No publicar exploits funcionales ni herramientas principalmente ofensivas. Los payloads de los benchmarks se usan como **datos**, nunca se ejecutan.
- Solo datos públicos anonimizados o sintéticos.
- **Atribución obligatoria:** todo código, dataset, librería o fragmento generado con IA se cita en la entrega. Lo llevamos en [`CITATIONS.md`](../CITATIONS.md) desde el primer commit.
