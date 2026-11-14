---
name: guard-contract
description: Contrato de check(texto, tarea, origen) -> (permitido, info), el mock en guard/mock.py (GUARD_MOCK=1) y cómo cambiar el contrato sin romper a los demás. Úsala al tocar guard/, al llamar a check() desde bench/ o un adaptador, o al proponer un campo nuevo en info.
---

# El contrato del guardián

Fuente de verdad: Contrato 1 en `docs/architecture.md`. Este resumen debe coincidir con él.

```python
from guard import check

permitido, info = check(salida_de_herramienta, tarea="Pay my rent bill for this month", origen="herramienta")
```

| Campo | Tipo | Significado |
|---|---|---|
| `permitido` | `bool` | `True` si no se marcó ningún trozo |
| `info["texto_limpio"]` | `str` | el texto con los trozos marcados reemplazados por `[contenido retirado por el guardián]` |
| `info["trozos_marcados"]` | `list[dict]` | cada uno con `texto`, `attack_score`, `drift_score` |
| `info["attack_score"]` | `float` 0–1 | el máximo entre los trozos |
| `info["drift_score"]` | `float` 0–1 o `None` | el del trozo con mayor `attack_score`; `None` sin tarea |
| `info["latencia_ms"]` | `float` | tiempo de `check()` |
| `info["origen"]` | `str` | `herramienta` (por defecto), `manifiesto` (descripción de una herramienta, MCPTox) o `usuario` |

- `tarea`: el primer mensaje del usuario de la conversación. Sin tarea, `drift_score` es `None` y se decide solo con `attack_score`.
- El guardián **sanea, no bloquea**: quien llama decide si usa `permitido` (descartar todo, `guard-detect`) o `texto_limpio` (retirar solo los trozos, `guard-sanitize`).

## Reglas del paquete

- `guard/` es Python puro: no importa AgentDojo ni `bench/`, no llama a un LLM, no tiene estado de otro módulo.
- El modelo de embeddings se carga una vez (carga perezosa en el primer `check()`) y funciona sin red después de descargarlo.
- Configuración (modelo, trozos, rutas) en `guard/config.py`; umbrales y dirección de ataque congelados en `guard/artifacts/` por el entrenamiento.
- Objetivo de latencia: menos de 300 ms por salida.

## El mock

Está en `guard/mock.py` y se activa con `GUARD_MOCK=1` (sin dependencias), con la firma final: marca oraciones que contienen "ignore", "ignora", "assistant:" o "asistente:" y devuelve todos los campos con puntajes falsos. `bench/` trabaja contra él desde el minuto uno. Cambiar el mock por la versión real (`docs/algorithm.md`) **no debe obligar a tocar `bench/`**.

## Cambiar el contrato

1. No se cambia en silencio. Se propone en el siguiente checkpoint (o en el grupo si es urgente).
2. Agregar un campo a `info` está bien si es opcional para quien lo lee.
3. Renombrar o quitar campos, o cambiar la firma: requiere acuerdo; en el mismo cambio se actualizan `guard/`, `bench/`, los tests y `docs/architecture.md`.

## AgentDojo usa el sentido opuesto

`PromptInjectionDetector.detect()` devuelve `True` cuando **hay** inyección: `return (not permitido), info["attack_score"]`. Ver la skill `agentdojo-adapter`.
