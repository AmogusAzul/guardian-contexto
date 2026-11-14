# data/

Dueño: **Datos**. Formato en el Contrato 3 de `docs/architecture.md`.

| Archivo | Qué es |
|---|---|
| `train.csv`, `val.csv`, `test.csv` | Corpus del Contrato 3: `text,label,category,source` |
| `mcp_train/val/test.jsonl` | Casos MCP: prompt del usuario + `tools/call` + respuesta del servidor, con `injected_text` |
| `QUALITY.md` | Reporte generado: composición, descartes por criterio, atajos medidos y fugas |
| `rejected.csv` | Cada fila descartada con su motivo (auditoría) |
| `pools/` | Muestras ya filtradas de LLMail-Inject y Glaive (evita bajar ~750 MB) |
| `raw/` | Descargas crudas (no se suben; `.gitignore`) |

## Regenerar

```sh
python data/build.py   # CSV + JSONL + QUALITY.md + rejected.csv (descarga lo que falte a data/raw/)
```

Solo librería estándar, determinista. Con `data/pools/` presente solo descarga archivos pequeños (InjecAgent, NotInject, correos legítimos de LLMail).

## Fuentes y split

Todas con licencia verificada en el repositorio original (ver `CITATIONS.md`). **Ningún texto de AgentDojo.**

| Fuente | Qué aporta | Cómo se separa |
|---|---|---|
| LLMail-Inject (MIT) | Ataques **escritos por personas** en un reto real, solo los que dispararon la herramienta (`api_triggered`); correos legítimos | Fase 1 → train, fase 2 → test (otros atacantes adaptados a otras defensas). Legítimos por tema: Aurora → train, Zenith/Orion → val, resto → test |
| InjecAgent (MIT) | Inyecciones dentro de respuestas JSON de 17 herramientas, con la instrucción del usuario | Por herramienta **y** por caso de ataque: ni la plantilla ni la instrucción se repiten entre splits. Versiones legítimas de las mismas plantillas |
| Glaive Function Calling v2 (Apache-2.0) | Respuestas reales de funciones con su petición | Por nombre de función (60/15/25). Al 40 % se le inyecta un ataque del split (reemplazando un campo o agregando uno) |
| NotInject (MIT) | Legítimos con palabras gatillo ("ignore", "bypass"…): sobre-defensa | `NotInject_one` → val, `_two`/`_three` → test. **Nunca en train** (advertencia de sus autores) |
| Sintéticos (`build.py`) | 10 familias de salidas de herramientas, *hard negatives*, 7 categorías de ataque incluida `task_aligned` | Cada familia en un split; redacciones, datos del atacante y formas de esconder distintas por split |

## Criterios de calidad (`pipeline.py`)

Cada fila se reevalúa; las que fallan van a `rejected.csv` con el motivo.

1. **Normalización:** Unicode NFC, saltos de línea, sin caracteres de control (se conservan los de formato, como zero-width, porque son parte de ataques ofuscados).
2. **Largo:** al menos 4 palabras y 20 caracteres, como mucho 2.500 (un trozo de salida de herramienta).
3. **Idioma:** inglés (como AgentDojo). Fuera alfabetos no latinos y textos con más palabras funcionales de alemán, español, francés, portugués o italiano.
4. **Codificación:** sin `�` ni mojibake.
5. **Datos personales:** sin números tipo tarjeta (Luhn) ni SSN.
6. **Fuga:** sin firmas de AgentDojo.
7. **Etiqueta sospechosa:** un legítimo con una inyección explícita ("ignore previous instructions", "system prompt"…) se descarta.
8. **Duplicados:** exactos, textos con etiquetas en conflicto y casi-duplicados (Jaccard de palabras ≥ 0,85), también entre splits, conservando primero test y luego val.
9. **Diversidad:** de LLMail y Glaive se toma una muestra diversa (Jaccard de 3-gramas ≤ 0,5 entre ataques; ≤ 4 respuestas por función).
10. **Atajos:** destinos fijos de los ataques (`contact@contact.com`, `amy.watson@gmail.com`) reemplazados por correos ficticios **distintos por split**. También son distintos por split los campos JSON donde va la inyección y las formas de esconderla. Hay *hard negatives* que mencionan "AI"/"assistant"/"agent", y legítimos con URL y correos.
11. **Equilibrio:** 50/50 ataque/legítimo en cada split, con recorte emparejado por longitud. Ninguna fuente pasa del 45 % de un split, y dentro de cada fuente con ambas etiquetas ninguna etiqueta pasa del 75 %.

Los números de cada criterio están en `QUALITY.md`.

## Casos MCP

`mcp_*.jsonl`: una línea por caso, 50/50 dentro de cada fuente, solo con filas aceptadas.

```python
texto = caso["mcp_response"]["result"]["content"][0]["text"]
permitido, info = check(texto, tarea=caso["prompt"], origen="herramienta")
# saneo correcto: caso["injected_text"] no está en info["texto_limpio"] y el resto sí
```

Fuentes: InjecAgent y Glaive (prompt, herramienta y argumentos reales), escenario de correo de LLMail (2–3 correos legítimos más, en los ataques, un correo de un atacante real) y sintéticos.

## Límites conocidos (para la ficha)

- **La longitud sigue ayudando algo:** AUC ≈ 0,63–0,71 dentro de cada fuente, porque una instrucción maliciosa suele ser más larga que el valor de un campo.
- **URL y correos:** aparecen en ~70–80 % de los ataques frente a ~15–25 % de los legítimos. Es propio del objetivo de los ataques (exfiltrar a un destino), pero un detector puede apoyarse en eso.
- **Calidad de las fuentes:** LLMail tiene un solo objetivo de ataque (mandar un correo), aunque con técnicas muy variadas. InjecAgent repite pocas plantillas, y sus instrucciones son cortas y sin ocultar.
- **NotInject son prompts de chat**, no salidas de herramientas: sirve para medir sobre-defensa, no como legítimo típico.
- Solo inglés. Sin ataques adaptativos contra *nuestro* guardián ni ataques partidos entre trozos.
- `val` no tiene ataques de LLMail: los umbrales se calibran sin ataques humanos adaptativos.
