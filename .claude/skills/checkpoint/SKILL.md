---
name: checkpoint
description: Prepara un checkpoint del equipo (fin de los bloques 2, 3 y 4): prueba de punta a punta del guardián en AgentDojo, revisión de contrato y citas, y resumen de qué funciona por rol. Úsala cuando alguien pida "checkpoint", "estado", "¿qué falta?" o antes de cambiar de bloque.
---

# Checkpoint

El plan del día está en `docs/team.md`. En cada checkpoint cada persona muestra algo **funcionando**, no "voy avanzando".

- **CP1 (10:45):** AgentDojo corre una tarea con el mock del guardián.
- **CP2 (13:00):** el guardián real corre en AgentDojo; hay líneas base en `results/`.
- **CP3 (15:00):** números finales en la ficha.

## Pasos

1. **Punta a punta:** las pruebas (`pytest`, si existen) y una tarea de AgentDojo con `guard-detect` y `guard-sanitize`. Si falla, eso va primero en el reporte.
2. **Contrato:** `guard/check.py` y `bench/` usan la misma firma e `info` (skill `guard-contract`).
3. **Citas:** dependencias, `data/` y los commits desde el último checkpoint contra `CITATIONS.md` (skill `cite`).
4. **Números:** el último archivo de `results/`, su commit y si el conjunto de prueba ya se usó.
5. **Preguntas abiertas:** las de `CLAUDE.md` que haya que decidir en este checkpoint.

## Reporte (corto, en español)

```
Checkpoint <n> · <hora> · bloque <n>
Punta a punta: OK / falla en <paso>
Por rol:
- Algoritmo: <qué funciona> / <qué bloquea>
- Datos: …
- Integración y benchmarks: …
- Pitch: …
Contrato: sin cambios / cambio propuesto: …
Citas pendientes: …
Siguiente bloque: <objetivo del bloque según team.md>
```

## Fechas que no se mueven

11:00 registro del equipo · 14:00 orden de pitches · 16:00 entrega sugerida · 17:00 cierre estricto · 17:10 pitches de 3 minutos. Si un checkpoint cae cerca, recuérdalas.
