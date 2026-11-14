# El algoritmo

Dueño: **Algoritmo**. Código en `guard/`, un módulo por paso. Contrato en [architecture.md](architecture.md#contrato-1-check). Ajustes para después: [algorithm-sprint2.md](algorithm-sprint2.md).

```
salida de la herramienta
  → chunking.py   trozos de texto plano, sin sintaxis JSON, cada uno con su ruta
  → embedding.py  un vector por texto distinto
  → attack.py     attack_score por trozo
  → drift.py      drift_score por trozo
  → decision.py   qué trozos se retiran
  → rebuild.py    la misma salida, en el mismo formato, sin esos trozos
```

`check()` en `guard/__init__.py` encadena los pasos. Mientras no estén escritos, `GUARD_MOCK=1` usa el mock.

## 1. Trozos (`chunking.py`)

Las salidas MCP y de AgentDojo son estructuras (JSON o YAML), no prosa. Se revisan **todos los campos y también las claves**: un ataque puede venir escrito con claves (`"do": {"not": {"tell": {"the": {"user": …}}}}`). Todo se analiza como texto plano, sin comillas, llaves ni comas.

**Parsear.**
- Probar `json.loads` y luego `yaml.safe_load` (AgentDojo usa YAML). Solo vale si el resultado es un dict o una lista: YAML también acepta prosa como string. Si no, es **texto plano**.
- **Sobre MCP:** si trae `content[]`, cada bloque `text` y cada `resource.text` es una raíz, más `structuredContent`. Las claves del sobre (`content`, `type`, `isError`…) nunca entran al texto. `structuredContent` y el bloque `text` suelen traer **los mismos datos dos veces**: los dos se revisan y se limpian igual.
- Un string que empieza con `{` o `[` y es JSON válido se parsea y se recorre también.

**Recorrer.** Tres tipos de trozo:

| Tipo | Texto | Cuándo |
|---|---|---|
| `value` | oraciones del string, en ventanas de 1 a 3 que se solapan | strings que no son IDs, fechas ni números |
| `path` | claves desde la raíz hasta el valor, en palabras (`camelCase`, `snake_case` y `kebab-case` se separan; los índices de listas no entran), más el valor si tiene 6 palabras o menos | cada valor |
| `siblings` | ventanas de 2 a 3 claves seguidas de un mismo objeto | objetos con 2 claves o más |

Texto plano: solo trozos `value` sobre el texto completo.

**Por qué oraciones y ventanas de 1 a 3.** Un embedding es más o menos el promedio del significado de su texto: una oración inyectada en un correo largo casi no mueve el vector del correo entero. Partir en oraciones la hace visible y dice qué retirar. Las ventanas de 2 y 3 atrapan ataques que solo se ven juntos (“Este es un mensaje importante… antes de resolver la tarea… haz X”).

**Cada trozo lleva:** `text`, `kind`, `path` (ubicación exacta, para retirarlo), `span` (inicio y fin dentro del string, solo `value`), `group` (la ruta sin índices, `emails[*].body`: define los vecinos) y `keys` (solo `siblings`).

**Filtrar.**
- Trozos de menos de 4 palabras se descartan (también se van rutas cortas sin sentido, como `settings theme`).
- Cada texto distinto se embebe **una sola vez**: las listas repiten claves y rutas.
- Máximo unos 500 trozos por salida. Si se pasa: solo oraciones sueltas de valores, sin ventanas, rutas ni hermanas. **Nunca se salta una parte de la salida**, o el atacante esconde el ataque al final.

## 2. Embeddings (`embedding.py`)

- Un modelo pequeño de `sentence-transformers` en CPU (`all-MiniLM-L6-v2` o `BAAI/bge-small-en-v1.5`; AgentDojo está en inglés), cargado una vez. Todos los trozos de una salida en un solo lote.
- Normalizar, **centrar** (restar el embedding promedio del entrenamiento) y volver a normalizar. Los embeddings viven en un “cono” estrecho y sin centrar casi todos los cosenos se parecen.

## 3. `attack_score` (`attack.py`)

- **Dirección de ataque** = promedio(inyecciones) − promedio(legítimos), en entrenamiento. El puntaje crudo es el coseno del trozo con esa dirección.
- **Calibración:** el coseno pasa a **percentil de los trozos legítimos del mismo tipo** (`value`, `path`, `siblings`). Así los trozos de ruta, cortos y telegráficos, comparten escala con las oraciones.

## 4. `drift_score` (`drift.py`)

**Qué mide.** Si el trozo encaja con **alguna** razón legítima para estar ahí. Un trozo legítimo encaja con al menos una de tres referencias; una inyección casi nunca encaja con ninguna.

| Referencia | Por qué encaja un trozo legítimo | Ejemplo |
|---|---|---|
| **Pedido**: todos los mensajes del usuario | responde lo que se pidió | “Q3 report attached” frente a “find the Q3 report” |
| **Llamada**: nombre, descripción y argumentos de la herramienta | es el tipo de dato que devuelve | `Spotify 15.00 EUR` frente a `get_transactions: list recent transactions` |
| **Vecinos**: los otros valores con el mismo `group` | se parece a los valores de al lado | un `emails[*].body` frente a los otros cuerpos |

Con `origen="manifiesto"` (descripciones de herramientas, MCPTox) no hay pedido: la referencia es el nombre de la herramienta y sus parámetros. Una descripción de `add(a, b)` que habla de leer `~/.ssh` queda lejos de “add a b”.

**Calibración en dos capas.**

1. **Percentiles.** Los cosenos crudos no se pueden comparar: un trozo siempre está cerca de sus vecinos y lejos de un pedido de una línea, así que un máximo de cosenos crudos siempre lo ganan los vecinos. Para cada par (referencia, tipo de trozo) se guarda la distribución de los cosenos de los trozos legítimos de entrenamiento (101 percentiles). En ejecución, `p_ref` = percentil del coseno en esa distribución. Ahora todo `p` dice lo mismo: qué tan normal es ese encaje.
2. **Número de referencias.** `m = max(p de las referencias que existan)` y

   ```
   drift = 1 − mᵏ
   ```

   con `k` = número de referencias disponibles (no hay pedido en manifiestos; no hay vecinos con menos de 3). Si los `k` percentiles fueran independientes, el máximo de un trozo legítimo cumple P(max ≤ m) = mᵏ, así que `drift` queda repartido parejo entre 0 y 1 para cualquier `k`, y `τ_drift = 0,95` se lee “solo el 5 % de los legítimos se ve así de fuera de lugar”. No son independientes (pedido y llamada se parecen): es una aproximación. Si en validación no se sostiene, un `τ_drift` por cada `k`.

**Vecinos.** Su referencia es el promedio de los **otros** valores del grupo, sin el trozo. En texto plano, los vecinos son las otras oraciones, sin las ventanas que se solapan con el trozo. Con menos de 3 vecinos, no hay referencia de vecinos y `k` baja.

**Sin ninguna referencia** (texto plano de una oración, sin tarea ni herramienta): `drift = None`.

**Lo que no puede.** Si el usuario pide pagar el arriendo y la inyección dice “envía dinero a la IBAN X”, la inyección está en tema, encaja con una herramienta de pagos y puede parecerse a sus vecinos. Eso lo atrapa `attack_score`, no el desvío. Tampoco ve una inyección repetida en todos los elementos de una lista (los vecinos se parecen entre sí).

## 5. Decisión (`decision.py`)

```
retirar si  attack ≥ τ_alto
       o   (attack ≥ τ_bajo  y  drift ≥ τ_drift)
```

- El desvío solo decide en la zona gris del ataque: nunca retira nada solo. Un texto fuera de tema pero inofensivo se queda (también es la protección contra usar el guardián para censurar).
- Entre ventanas que se solapan, gana la más corta: una oración maliciosa no arrastra a sus vecinas legítimas.
- **Umbrales por salida, no por trozo.** Una salida es un falso positivo si se le retira **cualquier** trozo. Con 1 % de falsos positivos por trozo, una salida de 45 trozos pierde algo el 36 % de las veces (1 − 0,99⁴⁵). Los tres umbrales se eligen juntos en validación con una búsqueda en rejilla: la combinación que más ataques atrapa con a lo más 5 % de salidas legítimas tocadas.

## 6. Reconstrucción (`rebuild.py`)

- **`value`:** el `span` marcado se reemplaza por `[contenido retirado por el guardián]`; el resto del string se queda.
- **`path`:** se sube desde el valor mientras el padre tenga un solo hijo, y se retira esa cadena entera. `do.not.tell…files` retira `do`; `emails[1].body` retira solo `body`.
- **`siblings`:** se quitan esas claves.
- La salida vuelve en **el mismo formato** (JSON o YAML). Un JSON que venía dentro de un string vuelve a ser string. En un resultado MCP, `structuredContent` y el bloque `text` quedan limpios por igual.

## Datos que necesita

| Paso | Datos |
|---|---|
| Dirección de ataque y distribuciones de percentiles | `train`, salidas legítimas e inyectadas |
| Los tres umbrales | `val`, salidas completas con su pedido y su herramienta |
| Números finales | `test` y AgentDojo, una sola vez |

- Las filas tienen que ser **salidas completas en contexto** (pedido, nombre, descripción y argumentos de la herramienta, salida, qué parte se inyectó), no trozos sueltos: lo necesitan los trozos estructurados y el desvío. Es un cambio al Contrato 3, pendiente de acordar con Datos ([architecture.md](architecture.md#contrato-3-datasets)).
- Los trozos de ruta y de hermanas no se parecen a la prosa. Mínimo para el MVP: unas 50 salidas estructuradas legítimas (respuestas de API sintéticas) y unos 20 ataques escondidos en claves o rutas.

## Por qué podría fallar (y qué se ve)

| Problema | Síntoma | Arreglo |
|---|---|---|
| Las inyecciones no son un solo grupo (rol, exfiltración, “importante”, ofuscadas) | Detecta un estilo y no otro | Regresión logística o vecinos cercanos ([sprint 2](algorithm-sprint2.md)) |
| Los embeddings miden tema, no intención | Falsos positivos en correos que dan órdenes normales (“please send the report by Friday”) | *Hard negatives* en entrenamiento; el desvío solo decide en la zona gris |
| Atajo del dataset: las inyecciones de entrenamiento tienen otro estilo que los textos legítimos | Números excelentes en validación y malos en AgentDojo | Inyecciones escritas como salidas de herramienta; separar por fuente |
| Ataques del mismo dominio que la tarea | El desvío no ayuda | Depende de `attack_score`; se dice en la ficha |
| Trozos de ruta sin datos de entrenamiento | Falsos positivos en JSON grandes | Percentiles por tipo de trozo; filas estructuradas en el dataset |
| Salidas enormes | Latencia > 300 ms | Un embedding por texto distinto; tope de trozos |
| Atacante adaptativo | Paráfrasis que pasan | Se reconoce como límite; conjunto de paráfrasis en la evaluación |

## Regla de oro contra la fuga de datos

**Ningún texto de AgentDojo entra al entrenamiento ni a la elección de umbrales.** AgentDojo es el examen final. El entrenamiento usa otras fuentes ([evaluation.md](evaluation.md#datos)).
