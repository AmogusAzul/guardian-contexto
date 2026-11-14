# El algoritmo

**Estado: versión 1 terminada** (decide solo con el ataque; el desvío queda para la versión 2). Falta reentrenar con los datos de banca pedidos a Datos ([data-banking-negatives.md](data-banking-negatives.md)) y congelar antes de las pruebas ([run-numbers.md](run-numbers.md)).

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

**Parsear.** Se prueba en este orden y gana el primero que da un dict o una lista:

| Formato | Cómo | Por qué (en `data/mcp_*.jsonl`) |
|---|---|---|
| `json` | `json.loads` | Glaive |
| `python` | `ast.literal_eval` (seguro: solo literales) | InjecAgent usa `{'a': 'b'}` |
| `yaml` | `yaml.safe_load` si el texto tiene forma de YAML: **alguna línea con sangría o que empieza con `- `**; o **plano**, 2 o más líneas y todas `clave: valor` con la clave sin espacios (`message: …` / `status: success`); o una sola línea `clave: 'valor entre comillas'`. Además: **sin claves repetidas** (PyYAML las pisa en silencio) y al menos la mitad de las claves **de arriba** con forma de campo (sin espacios; más adentro valen claves como `1:00 PM`). Una sola clave arriba (`emails:`) o una lista de un elemento valen. Los textos largos que `safe_dump` parte en varias líneas y los escapes (`Bogot\xE1`) los resuelve el propio parser | AgentDojo devuelve `yaml.safe_dump`. En el corpus de Datos con ese formato ([yaml-findings.md](yaml-findings.md)): 613 de 620 salidas se reconocen como YAML (antes 502) y todos los ataques en claves tienen su trozo `path`. Siguen como `text` el YAML de una sola línea sin comillas (`data: …`, no se distingue de `Note: …`) y la prosa que también parsea como YAML: un chat `Nombre: mensaje` con nombres repetidos o con espacios, un título seguido de viñetas. Se leen como YAML eventos de calendario `Event: …` / `Date: …`, sin perder nada |
| `loose` | empieza con `{` o `[` pero no parsea: cortar en `'clave':` / `"clave":`, quitar comillas y llaves de cada valor, guardar sus posiciones | 45 casos: **la inyección rompió las comillas** del JSON |
| `text` | todo lo demás | correos, chats, documentos |

- **Sobre MCP:** si trae `content[]`, cada bloque `text` y cada `resource.text` es una raíz, más `structuredContent`. Las claves del sobre (`content`, `type`, `isError`…) nunca entran al texto. `structuredContent` y el bloque `text` suelen traer **los mismos datos dos veces**: los dos se revisan y se limpian igual.
- Un string dentro de la estructura que empieza con `{` o `[` y es JSON válido se parsea y se recorre también.

**Recorrer.** Dos tipos de trozo:

| Tipo | Texto | Cuándo |
|---|---|---|
| `value` | oraciones del string, en ventanas de 1 a 3 que se solapan | strings que no son IDs, fechas ni números |
| `path` | claves desde la raíz hasta el valor, en palabras (`camelCase`, `snake_case` y `kebab-case` se separan; los índices de listas no entran), más el valor si tiene 6 palabras o menos | cada valor |

**Texto (y cada string largo).** Primero **bloques** (separados por `---` o una línea en blanco: un correo, un documento), después líneas, después oraciones. Dentro de una línea también se corta, sin buscar palabras de ataque, donde un texto pegado sin punto suele empezar algo nuevo: antes de una etiqueta o comentario HTML, antes de un comentario de markdown (`[//]: #`), tras un punto seguido de `>`, `—` o un inicio de Markdown (`**`, `*`, `-`, `` ` ``, `_`, un número), y tras una coma seguida de una palabra con mayúscula (`…new flavor, Please…`). Las ventanas de 1 a 3 **no cruzan bloques**. Los bloques de un mismo texto son vecinos entre sí para el desvío. Además, **cada valor y cada bloque entero** es un trozo si tiene 120 palabras o menos: LLMail inyecta correos enteros y Glaive reemplaza campos enteros (120 palabras cabe en lo que lee MiniLM, unos 256 tokens).

**Limpiar el texto antes de embeber** (las posiciones siguen apuntando al original):
- Unicode NFC y espacios colapsados.
- Fuera los caracteres de ancho cero (ofuscación).
- De los comentarios y etiquetas HTML (`<!-- -->`, `<span style="display:none">`), de los comentarios de markdown (`[//]: #`) y del formato Markdown (`**`, `__`, `` ` ``, y `>`, viñetas o `1.` al comienzo) se quitan solo las marcas: el texto de adentro suele ser el ataque. `<|system|>` y parecidos se quedan.
- Un trozo `value` lleva solo el valor, sin su clave: la clave ya va en el trozo `path`.

**Por qué oraciones y ventanas de 1 a 3.** Un embedding es más o menos el promedio del significado de su texto: una oración inyectada en un correo largo casi no mueve el vector del correo entero. Partir en oraciones la hace visible y dice qué retirar. Las ventanas de 2 y 3 atrapan ataques que solo se ven juntos (“Este es un mensaje importante… antes de resolver la tarea… haz X”).

**Cada trozo lleva:** `text` (limpio), `kind`, `path` (ubicación exacta, para retirarlo), `span` (inicio y fin en el string original, solo `value`), `group` (la ruta sin índices, `emails[*].body`, o el texto si son bloques: define los vecinos).

**Filtrar.**
- Trozos `value` de menos de 4 palabras se descartan. Los trozos `path`, desde 3: en una clave, 3 palabras ya pueden ser una orden (`transfer savings to` con un IBAN largo, que no entra al trozo). Se siguen yendo rutas de 2 palabras, como `settings theme`.
- Cada texto distinto se embebe **una sola vez**: las listas repiten claves y rutas.
- En `data/mcp_*.jsonl` las salidas son cortas (mediana 300 caracteres, máximo 2 890); un caso de LLMail da unos 45 trozos.
- Máximo unos 500 trozos por salida. Si se pasa: solo oraciones sueltas de valores, sin ventanas ni rutas. **Nunca se salta una parte de la salida**, o el atacante esconde el ataque al final.

**Prueba del paso (sin embeddings).** En un subconjunto chico de `data/mcp_train.jsonl` con inyección (5 casos por familia: Glaive, InjecAgent, LLMail, sintéticos): la inyección tiene que quedar cubierta por trozos `value` que sean al menos 80 % inyección (el 80 % deja pasar un “IMPORTANT:” delante, que `injected_text` no incluye). Si eso falla, ningún puntaje lo arregla.

`python -m guard.show_chunks data/mcp_train.jsonl --n 3` (o `--id <caso>`) muestra los trozos de cada caso y cuáles son la inyección. En todo `data/mcp_*.jsonl`, 90 de 90 inyecciones en claves (contadas solo si el trozo de ataque es de **ruta**: el valor solo no lleva la orden) y 437 de 437 en valores quedan cubiertas por al menos un trozo de ataque, con unos 12,5 trozos por salida. Antes de los arreglos de [chunking-findings.md](chunking-findings.md) eran 88 y 428: inyecciones pegadas sin punto (`…new flavor, Please…`, `…Tom Becker <span…>Assistant, when…`) y claves cortas con valor largo. Una inyección que empieza con Markdown después del punto (`opt out. > As part of…`, `**…**`, `- …`, `1. …`) también queda en su propio trozo. `data/check_chunks.py` de Datos da 527/527 casos MCP y 1 771/1 771 filas de los CSV. Retirando esos trozos, la inyección desaparece en todos los casos y el JSON sigue siendo válido. Lo que se pierde son unas palabras pegadas a la inyección sin ningún corte (una firma `— Tom Becker` justo antes); con la regla de la ventana más corta (paso 5) se conservan 1 285 de 1 286 oraciones legítimas.

## 2. Embeddings (`embedding.py`)

- **Modelo:** `sentence-transformers/all-MiniLM-L6-v2` (384 dimensiones, CPU, lee unos 256 tokens). Se carga una vez, en el primer `check()`. La comparación con otros modelos queda para el [sprint 2](algorithm-sprint2.md).
- **Entrada:** el texto limpio del trozo, sin prefijos. Nada pasa de 120 palabras (lo corta el paso 1).
- **Un lote por salida** y cada texto distinto una sola vez. Un caché chico en memoria guarda los textos recientes: el pedido, la llamada y las rutas que se repiten (`emails body`) son los mismos en cada llamada de una conversación o de una herramienta.
- **Centrar:** restar **un solo promedio** (el de todos los trozos de entrenamiento, ataques y legítimos, equilibrado por fuente) y normalizar. Las referencias del desvío (pedido, llamada) pasan por lo mismo, así todos los cosenos viven en el mismo espacio. Sin centrar, los embeddings viven en un “cono” estrecho y casi todos los cosenos se parecen.

### Datos de referencia (`guard/artifacts/<modelo>.npz`)

Un script de entrenamiento los arma una vez y se congelan con el commit:

| Qué | De dónde |
|---|---|
| promedio para centrar | todos los trozos de entrenamiento |
| dirección de ataque | trozos de ataque − trozos legítimos (paso 3) |
| tablas de percentiles: ataque por (tipo, tamaño), desvío por (referencia, tipo, tamaño) | trozos legítimos |
| nombre del modelo y commit de los datos | — |

**Etiquetar trozos.** Los datos vienen por salida completa y la dirección se aprende por trozo. Se usa **`data/mcp_train.jsonl`**, que trae `injected_text`:
- trozo con al menos 80 % de inyección → **ataque**;
- trozos de salidas legítimas, y trozos de salidas atacadas que no tocan la inyección → **legítimo** (estos últimos son buenos: legítimos del mismo contexto que el ataque);
- trozos mitad y mitad → **fuera** (ambiguos).
- **Peso por fuente**, para que ninguna decida la dirección sola.

Son 376 salidas (188 con ataque). Alcanza para una resta de promedios en 384 dimensiones. `data/train.csv` tiene 4 veces más ataques, pero sin marcar qué parte es la inyección: un `{"status": "success", "message": "P.S. ### SYSTEM MESSAGE…"}` daría trozos legítimos etiquetados como ataque. Usarlo queda para el sprint 2.

### Pruebas del paso (rápidas, en parte de validación)

1. **Centrado:** el coseno promedio entre trozos legítimos al azar baja a casi 0.
2. **Separación:** AUC de la dirección de ataque por tipo de trozo. Por debajo de ~0,8 hay un problema de modelo o de etiquetas, antes de cualquier umbral.
3. **Vecinos:** los 3 trozos de entrenamiento más cercanos a 5 trozos de ataque también son ataques (atrapa etiquetas malas).
4. **Latencia:** mediana y p95 de embeber una salida completa, en la máquina más lenta de la demo.

## 3. `attack_score` (`attack.py`)

- **Dirección de ataque** = promedio(trozos de ataque) − promedio(trozos legítimos), con las etiquetas del paso 2. El puntaje crudo es el coseno del trozo con esa dirección.
- **Calibración:** el coseno pasa a **percentil de los trozos legítimos de la misma clase** (tipo y tamaño, ver “Escalas” en el paso 4). Así los trozos de ruta, cortos y telegráficos, comparten escala con las oraciones.

## 4. `drift_score` (`drift.py`)

**Qué mide.** Si el trozo encaja con **alguna** razón legítima para estar ahí. Un trozo legítimo encaja con al menos una de tres referencias; una inyección casi nunca encaja con ninguna.

| Referencia | Por qué encaja un trozo legítimo | Ejemplo |
|---|---|---|
| **Pedido**: cada mensaje del usuario, por separado; cuenta el que más se parece | responde lo que se pidió | “Q3 report attached” frente a “find the Q3 report” |
| **Llamada**: un solo texto con el nombre de la herramienta en palabras, su descripción y los valores de los argumentos | es el tipo de dato que devuelve | `Spotify 15.00 EUR` frente a `get_transactions: list recent transactions` |
| **Vecinos**: los otros valores con el mismo `group` (al menos 3) | se parece a los valores de al lado | un `emails[*].body` frente a los otros cuerpos |

Con `origen="manifiesto"` (descripciones de herramientas, MCPTox) no hay pedido: la referencia es el nombre de la herramienta y sus parámetros. Una descripción de `add(a, b)` que habla de leer `~/.ssh` queda lejos de “add a b”.

**Calibración en dos capas.**

1. **Percentiles.** Los cosenos crudos no se pueden comparar (ver “Escalas” abajo): un trozo siempre está cerca de sus vecinos y lejos de un pedido de una línea, así que un máximo de cosenos crudos siempre lo ganan los vecinos. Para cada clase se guarda la distribución de los cosenos de los trozos legítimos de entrenamiento. En ejecución, `p_ref` = percentil del coseno en esa distribución. Ahora todo `p` dice lo mismo: qué tan normal es ese encaje.
2. **Número de referencias.** `m = max(p de las referencias que existan)` y

   ```
   drift = 1 − mᵏ
   ```

   con `k` = número de referencias disponibles (no hay pedido en manifiestos; no hay vecinos con menos de 3). Si los `k` percentiles fueran independientes, el máximo de un trozo legítimo cumple P(max ≤ m) = mᵏ, así que `drift` queda repartido parejo entre 0 y 1 para cualquier `k`, y `τ_drift = 0,95` se lee “solo el 5 % de los legítimos se ve así de fuera de lugar”. No son independientes (pedido y llamada se parecen): es una aproximación. Si en validación no se sostiene, un `τ_drift` por cada `k`.

**Vecinos.** El coseno con los vecinos es el **promedio de los cosenos con cada vecino**, no el coseno con su vector promedio: el promedio de 20 vectores es más “liso” que el de 3 y el coseno con él crece con la cantidad; el promedio de cosenos no depende de cuántos son. Nunca se cuenta el trozo mismo. En texto, los vecinos son los otros bloques; tampoco cuentan las ventanas que se solapan con el trozo. Con menos de 3 vecinos, no hay referencia de vecinos y `k` baja.

**Escalas.** Lo que mueve los cosenos crudos, y qué se hace con cada cosa:

| Fuente | Por qué cambia la escala | Qué se hace |
|---|---|---|
| Referencia (pedido, llamada, vecinos) | los vecinos siempre parecen más cerca que un pedido de una línea | una tabla de percentiles por referencia |
| Tipo de trozo (`value`, `path`) | las rutas son texto corto y telegráfico | una tabla por tipo |
| Tamaño del trozo | los trozos largos promedian su significado y quedan más cerca de todo | una tabla por tamaño: 1 oración, 2–3 oraciones, valor o bloque entero. Si una clase tiene menos de unos 200 ejemplos, usa la tabla de su tipo |
| Cantidad de vecinos | el coseno con un promedio crece con la cantidad | promedio de cosenos (arriba) |
| Herramienta o dominio | hay herramientas cuyos datos están naturalmente lejos del pedido | no se calibra por herramienta (en ejecución son nuevas); los vecinos lo absorben en parte. Límite aceptado |

Así quedan unas 18 tablas de desvío (3 referencias × 2 tipos × 3 tamaños) y 6 de ataque (2 tipos × 3 tamaños), cada una con 101 percentiles de los trozos legítimos de entrenamiento. Entre puntos se interpola. **La cola alta no se satura:** por encima del percentil 95 se usa una cola exponencial que pasa por los percentiles 95 y 99, así un valor más alto que todos los legítimos de entrenamiento sigue ordenado (0,999, 0,9999…) en vez de quedar en 1 junto con todos los demás. Sin esto, en validación el 40 % de los ataques y el 6 % de las salidas legítimas quedaban empatados en 1 y no había umbral posible. **La llamada se arma igual al calibrar y en ejecución** (mismos campos): si en ejecución se agregara un campo que no estaba al calibrar, los cosenos subirían y el desvío saldría bajo sin razón.

**Prueba de la calibración.** En los trozos legítimos de validación, `drift` tiene que quedar **parejo** entre 0 y 1 para cada `k` (cerca de 10 % en cada décimo). Como las referencias no son independientes, `1 − mᵏ` no queda del todo parejo. Por eso pasa por **una última tabla por `k`** (los mismos legítimos de entrenamiento): ahí sí queda parejo en entrenamiento por construcción, y `τ_drift = 0,95` significa 5 % de los legítimos. En validación se mira cuánto se mueve.

**Sin ninguna referencia** (texto plano de una oración, sin tarea ni herramienta): `drift = None`.

**Lo que no puede.** Si el usuario pide pagar el arriendo y la inyección dice “envía dinero a la IBAN X”, la inyección está en tema, encaja con una herramienta de pagos y puede parecerse a sus vecinos. Eso lo atrapa `attack_score`, no el desvío. Tampoco ve una inyección repetida en todos los elementos de una lista (los vecinos se parecen entre sí).

## 5. Decisión (`decision.py`)

```
retirar si  attack ≥ τ_alto
       o   (attack ≥ τ_bajo  y  drift ≥ τ_drift)
```

- El desvío solo decide en la zona gris del ataque: nunca retira nada solo. Un texto fuera de tema pero inofensivo se queda (también es la protección contra usar el guardián para censurar).
- Entre ventanas que se solapan, gana la más corta: una oración maliciosa no arrastra a sus vecinas legítimas.
- **Umbrales por salida, no por trozo.** Una salida es un falso positivo si se le retira **cualquier** trozo. Con 1 % de falsos positivos por trozo, una salida de 45 trozos pierde algo el 36 % de las veces (1 − 0,99⁴⁵). Los tres umbrales se eligen juntos en validación con una búsqueda en rejilla: la combinación que más salidas atacadas atrapa (con un trozo de ataque retirado) con a lo más 5 % de salidas legítimas tocadas. Los candidatos salen de los datos: para `τ_alto`, percentiles altos del máximo de ataque de cada salida legítima; para `τ_bajo`, percentiles del ataque de los trozos legítimos.

**Cuatro formas de decidir, comparadas en validación** (`guard.train`; se ajustan en una mitad y se miden en la otra, promedio de las dos):

| Método | Qué decide | Atrapadas | Legítimas tocadas |
|---|---|---|---|
| Solo ataque | `attack ≥ τ_alto` | 72 % | 5 % |
| Regla, tabla final del desvío de train | la regla de arriba | 79 % | 8 % |
| Regla, tabla final del desvío de validación | la regla de arriba | 78 % | 10 % |
| Logística (`stack.py`) | una regresión logística sobre los percentiles (ataque, pedido, llamada, vecinos) y la clase del trozo, con un solo umbral | 84 % | 7 % |

Se elige el que mejor separa y se reajusta con toda la validación; el método y sus umbrales quedan en el archivo de referencia (`method`). **Versión 1: solo ataque** (`τ_alto = 0,9936`): es el único que se mantiene en 5 % de legítimas tocadas en la otra mitad. **En la versión 1 el desvío no se usa:** `check()` no lo calcula (`drift_score` es `None`) y la regla queda en `attack ≥ τ_alto`. Las otras formas atrapan más pero se pasan del 5 % al cambiar de mitad; la estrategia de clasificación se revisa en la versión 2 ([algorithm-sprint2.md](algorithm-sprint2.md)). `drift.py`, `stack.py` y la comparación de `guard.train` se quedan para eso.

`check()` de punta a punta en `data/mcp_val.jsonl` con esa versión: 93 de 111 inyecciones retiradas, 5 de 111 salidas legítimas tocadas, latencia mediana 97 ms (p95 293 ms) después de la primera llamada, que carga el modelo (unos 15 s).

## Entrenar y medir (`python -m guard.train`)

Arma `guard/artifacts/<modelo>.npz` con `data/mcp_train.jsonl` (pasos 2 a 4), compara los métodos del paso 5 en `data/mcp_val.jsonl`, guarda el elegido con sus umbrales e imprime las pruebas: centrado, AUC por clase, la comparación y la latencia. Tarda unos minutos en CPU. Si se cambia el troceo o los datos, hay que volver a correrlo.

## 6. Reconstrucción (`rebuild.py`)

- **`value`:** el `span` marcado se reemplaza por `[contenido retirado por el guardián]`; el resto del string se queda.
- **`path`:** se sube desde el valor mientras el padre tenga un solo hijo, y se retira esa cadena entera. `do.not.tell…files` retira `do`; `emails[1].body` retira solo `body`. En un objeto se **borra la clave** (la clave puede ser el ataque); en una lista el elemento pasa a ser el aviso, para no mover los otros índices. Nunca se sube por encima de una raíz (la salida, un bloque MCP, un JSON dentro de un string).
- **Copias:** un texto que aparece en varios lugares (por ejemplo `structuredContent` y el bloque `text` de MCP) se embebe una vez pero se retira en todos.
- Spans marcados que se tocan, o que solo separa espacio, llevan un solo aviso.
- `text` y `loose`: se reemplaza en las posiciones guardadas del string original, así el formato no cambia. `json`, `python` y `yaml`: se rearma la estructura y se vuelve a escribir (puede cambiar los espacios; `python` sale como JSON; en `yaml` los strings de varias líneas salen como bloque `|` y no se parten líneas largas).
- Un JSON que venía dentro de un string vuelve a ser string. En un resultado MCP, `structuredContent` y el bloque `text` quedan limpios por igual.

## Datos que necesita

| Paso | Datos |
|---|---|
| Dirección de ataque y distribuciones de percentiles | `train`, salidas legítimas e inyectadas |
| Los tres umbrales | `val`, salidas completas con su pedido y su herramienta |
| Números finales | `test` y AgentDojo, una sola vez |

- Las filas tienen que ser **salidas completas en contexto** (pedido, nombre, descripción y argumentos de la herramienta, salida, qué parte se inyectó), no trozos sueltos: lo necesitan los trozos estructurados y el desvío. Es un cambio al Contrato 3, pendiente de acordar con Datos ([architecture.md](architecture.md#contrato-3-datasets)).
- Los trozos de ruta no se parecen a la prosa: hacen falta ataques escondidos en claves y legítimos con claves largas ([data-key-attacks.md](data-key-attacks.md)).

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
