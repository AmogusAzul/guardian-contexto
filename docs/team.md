# Equipo: roles, cronograma y reglas

Los roles están pensados para la rúbrica ([hackathon.md](hackathon.md)): Algoritmo y Datos construyen la defensa (Impacto), Integración la mide contra líneas base y la deja reproducible (Ejecución), Pitch la hace entendible en 2 minutos (Presentación). Nadie espera a nadie: todos trabajan contra el mock de `check()` y los contratos de [architecture.md](architecture.md). Quien termine antes ayuda al rol que esté frenando, sin cambiar de dueño.

## Roles

### Algoritmo (líder)
- **Hace:** el paquete `guard/`: trozos, embeddings, puntajes, umbrales y saneo ([algorithm.md](algorithm.md)).
- **Primera hora:** el mock de `check()` ya está; elegir el modelo de embeddings y medir cuánto tarda en una salida de herramienta típica.
- **Listo cuando:** `check()` real cumple el Contrato 1, tarda menos de 300 ms y supera al filtro de palabras clave en `data/val.csv`.

### Datos
- **Hace:** los datasets del Contrato 3: inyecciones escritas como salidas de herramientas, salidas legítimas, *hard negatives*, splits por fuente, y las descripciones limpias para MCPTox.
- **Primera hora:** reunir fuentes (un dataset público de inyección, por ejemplo `deepset/prompt-injections`, y plantillas propias) con su licencia en `CITATIONS.md`; entregar las primeras 20 filas, con 5 *hard negatives*.
- **Listo cuando:** `train/val/test` tienen al menos 150 inyecciones y 150 legítimos (30 *hard negatives*), separados por fuente, sin ningún texto de AgentDojo.

### Integración y benchmarks
- **Hace:** el repo ejecutable, AgentDojo con la clave de OpenAI, el adaptador (`guard-detect` y `guard-sanitize`), las líneas base, `results/`, el README con los comandos y `bench/demo.py`.
- **Primera hora:** `pip install agentdojo`, configurar la clave y correr 1 tarea sin defensa (prueba de humo); medir tokens por caso.
- **Listo cuando:** un solo comando del README reproduce la tabla de la ficha.

### Pitch
- **Hace:** registro del equipo, la ficha técnica (2 páginas), el resumen (150–250 palabras), el guion de 3 minutos, el video de la demo, `CITATIONS.md` al día y la entrega. Va a todos los checkpoints y conoce todo el sistema ([pitch.md](pitch.md)).
- **Primera hora:** **registrar al equipo antes de las 11:00**; pedir la plantilla oficial de la ficha; boceto de la ficha con amenaza, defensa y diagrama.
- **Listo cuando:** la ficha tiene los números reales de `results/` y todo se entregó a las 16:00.

**Equipo de 5:** la quinta persona hace la “cosa encima” que vuelve la idea adoptable: un proxy MCP que pasa las respuestas de cualquier servidor MCP por `check()` (opcional; no se arriesga la evaluación por esto).

## Cronograma (sábado 14 de noviembre)

| Bloque | Algoritmo | Datos | Integración | Pitch |
|---|---|---|---|---|
| **1 · 9:00–10:00 Arranque** | modelo de embeddings y latencia | fuentes, licencias, 20 filas | AgentDojo instalado, 1 tarea sin defensa | **registro**, pedir plantilla, boceto de ficha |
| **2 · 10:00–10:45 Interfaces** | `check()` v0 sobre las 20 filas | formato fijo, splits por fuente | adaptador con el mock; corre `guard-detect` y `guard-sanitize` en 1 tarea | guion preliminar de 3 min |
| **3 · 10:45–13:00 Construcción** | `check()` v1 real | dataset completo | líneas base completas (sin defensa, palabras clave, DeBERTa) en la suite | ficha v1: amenaza, defensa, diagrama |
| **4 · 13:00–15:00 Evaluación** | umbrales en validación; congelar | MCPTox limpio (si alcanza) | corridas finales con el guardián; `demo.py` y capturas | resultados en la ficha; orden del pitch (14:00) |
| **5 · 15:00–16:00 Entregar** | límites y uso dual con Pitch | `CITATIONS.md` completo | README reproducible; congelar código | **entrega a las 16:00** |
| **6 · 16:00–17:00 Ensayo** | — | — | — | dos ensayos con la ficha en pantalla; todos responden las preguntas probables |

**Checkpoints** al final de los bloques 2, 3 y 4: cada persona muestra algo **funcionando**.
- **CP1 (10:45):** AgentDojo corre una tarea con el mock del guardián.
- **CP2 (13:00):** el guardián real corre en AgentDojo; hay líneas base en `results/`.
- **CP3 (15:00):** números finales en la ficha.

## Reglas del equipo

1. Nadie se queda atascado más de 30 minutos sin preguntar.
2. Primero la versión fea de punta a punta, después se mejora.
3. Los contratos no cambian sin avisar en un checkpoint.
4. Todo lo que se use (código, datos, texto generado con IA) se cita en `CITATIONS.md` en el momento.
5. Todos explican en 30 segundos “¿cómo funciona?” y “¿cuál es la limitación principal?”.
