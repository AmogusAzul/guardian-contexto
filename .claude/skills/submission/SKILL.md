---
name: submission
description: Lista de verificación de la entrega del hackathon (repo, README, CITATIONS.md, results/, ficha técnica de 2 páginas, resumen de 150–250 palabras) y del pitch de 3 minutos. Úsala desde el bloque 5 (15:00), al escribir el README final o al revisar si el repo está listo para el jurado.
---

# Entrega

Formulario: https://www.aisafetycolombia.org/defacchackathon/entregar (abre 7:00; **entregar a las 16:00, cierre estricto 17:00**; correcciones a equipo@aisafetycolombia.org). La ficha, el resumen y el pitch son de Pitch; el repo es de todos. Detalle en `docs/pitch.md` y `docs/hackathon.md`.

## El jurado califica (1 a 5 cada uno, mismo peso; empate → Impacto)

- **Impacto e innovación:** riesgo importante y poco atendido; enfoque original que un equipo real podría adoptar.
- **Ejecución:** funciona de punta a punta, se puede reproducir, evaluado contra una línea base, con límites y uso dual.
- **Presentación:** un jurado lo entiende en 2 minutos; ficha concisa con los resultados clave.

## Repo

- [ ] `README.md`: qué es (2 líneas), cómo instalar, **el comando exacto que reproduce la tabla de la ficha** (AgentDojo y detector) y dónde quedan los resultados. Un clon limpio funciona siguiendo solo el README.
- [ ] `results/` con la corrida final (fecha y commit) que coincide con la ficha.
- [ ] `CITATIONS.md` completo (skill `cite`).
- [ ] Sin claves de API, `.env` ni datos personales en el historial.
- [ ] Repo público (o acceso para el jurado) y el enlace probado en una ventana privada.
- [ ] Video de la demo (`bench/demo.py`: salida cruda contra salida limpia) enlazado.

## Formulario

- [ ] Nombre del equipo, integrantes (2 a 5) con el correo con que aplicaron, título, Track 1.
- [ ] Resumen de **150 a 250 palabras** (contar las palabras).
- [ ] Enlace al repo (y al video).
- [ ] Ficha técnica en PDF: **máximo 2 páginas y 10 MB**, con la plantilla oficial si la organización la entregó: amenaza, defensa, metodología, resultados cuantitativos, límites y riesgo de uso dual.

## Pitch (17:10, 3 minutos, sin diapositivas)

Se proyecta la ficha y el jurado la lee. Guion y preguntas probables en `docs/pitch.md`. Dos ensayos completos antes de las 17:00, y todos saben responder en 20 segundos: "¿y un atacante que reescribe el ataque?", "¿por qué embeddings y no un LLM juez?", "¿cuánto daña las tareas normales?", "¿cómo lo reproduzco?".
