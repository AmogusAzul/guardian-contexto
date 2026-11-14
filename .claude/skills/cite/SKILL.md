---
name: cite
description: Registra en CITATIONS.md el código, datos, librerías, modelos y texto generados con IA o tomados de terceros. Úsala cada vez que se agrega una dependencia, un dataset, un modelo de embeddings, código copiado o adaptado, o un archivo escrito total o parcialmente por una IA (incluido lo que escribes tú), y antes de cada checkpoint y de la entrega.
---

# Citar todo

Regla del hackathon: "todo código, dataset, librería o fragmento generado con IA debe estar claramente documentado y citado en la entrega". Una cita que falta se nota en la ficha y resta puntos de ejecución y de presentación.

## Cuándo

- Agregas una dependencia (`pyproject.toml`, `requirements.txt`): `sentence-transformers`, `agentdojo`, etc.
- Usas un dataset, un benchmark o un modelo (Hugging Face, GitHub, artículo).
- Copias o adaptas código de otro repo, de la documentación o de una respuesta en internet.
- Escribes o modificas un archivo con ayuda de una IA. **Esto incluye todo lo que escribe Claude Code.**

Se cita en el mismo cambio que introduce la cosa, no al final del día.

## Formato de `CITATIONS.md`

Cuatro secciones, siempre en este orden. Si el archivo no existe, créalo con ellas.

```markdown
# Citas

## Datos y benchmarks
| Nombre | Fuente (URL) | Licencia | Uso en el proyecto |
|---|---|---|---|
| deepset/prompt-injections | https://huggingface.co/datasets/deepset/prompt-injections | <verificar> | filas `source=deepset` de data/*.csv |

## Modelos
| Nombre | Fuente | Licencia | Uso |

## Librerías y código de terceros
| Nombre | Versión | Licencia | Uso / archivos |

## Código y texto generados con IA
| Archivos o módulo | Herramienta y modelo | Qué hizo la IA | Revisado por |
| guard/check.py | Claude Code (claude-opus-5-5) | primera versión del chunking | <rol> |
```

## Reglas

- **Licencia:** cópiala del repo o de la ficha del dataset. Si no hay (por ejemplo MCPTox), escribe `sin licencia declarada; usado solo como datos de evaluación`. Nunca inventes una licencia.
- **IA:** una fila por módulo o archivo, no por línea. Nombra la herramienta y el modelo exacto. Si un humano lo revisó, el rol que lo revisó; si no, `sin revisar`.
- **Datos derivados:** si traduces, parafraseas o generas filas con IA, la columna `source` del dataset lo dice (`traducido`, `generado_ia`) y aquí va una fila que explique cómo.
- Cuando cites tu propio trabajo en este repo, agrega también la línea `Co-authored-by` o la nota que pida el equipo en el mensaje del commit.

## Antes de la entrega

Recorre las dependencias, `data/` y el historial de git (`git log --stat`) y verifica que todo lo de terceros o hecho con IA esté en la tabla. La ficha técnica apunta a `CITATIONS.md`.
