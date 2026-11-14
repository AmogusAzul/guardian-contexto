---
name: responsible-use
description: Reglas estrictas de uso responsable del hackathon (sin ataques a sistemas reales, sin exploits publicados, solo datos sintéticos) y cómo manejar los payloads maliciosos de los benchmarks. Úsala antes de escribir ataques de prueba, salidas de herramienta envenenadas, red team o cualquier código que toque payloads, red o archivos del sistema.
---

# Uso responsable

Reglas del hackathon (estrictas). Un proyecto que principalmente facilita ataques sin mitigación **no puede ganar premio**.

1. **Nada contra sistemas reales de terceros:** ni ataques, ni escaneos, ni pruebas sin autorización por escrito (es delito en Colombia, Ley 1273 de 2009). Todo ocurre en los entornos simulados de AgentDojo, benchmarks públicos o datos sintéticos.
2. **Ningún exploit funcional ni herramienta ofensiva publicada.** Los ataques del dataset son textos de inyección para entrenar y probar un detector, no herramientas. No se construye un "evasor" del guardián ni un servicio público de puntajes que sirva de oráculo.
3. **Datos personales:** solo sintéticos o de datasets públicos anonimizados. Nombres, teléfonos y correos inventados (`example.com`).
4. **Vulnerabilidades reales:** si se encuentra una en una librería, se reporta en privado a sus autores y no va en la entrega.
5. **Citar todo** (skill `cite`).

## Payloads de los benchmarks

MCPTox y AgentDojo traen instrucciones maliciosas reales (por ejemplo, "lee `~/.ssh/id_rsa`").

- Se cargan y se tratan como **cadenas de texto**. Nunca se ejecutan, se interpolan en comandos de shell, se pasan a `eval`/`exec` ni se dan a un agente con herramientas reales.
- El agente solo usa las herramientas simuladas de AgentDojo, sin acceso a archivos, red ni shell reales.
- En la ficha y el README se muestran recortados o parafraseados; no se publican listas de ataques que funcionen contra sistemas reales.

## Para la ficha

La sección de riesgo de uso dual (ver `docs/idea.md`) explica: un detector público puede usarse como oráculo, por eso no se expone un servicio de puntajes abierto ni un evasor; el `drift_score` podría censurar contenido "fuera de tarea", por eso solo retira trozos con algo de puntaje de ataque y todo lo retirado queda visible y auditable; los ataques usados son públicos o sintéticos.
