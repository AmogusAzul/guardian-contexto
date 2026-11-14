# Cómo sacar los números (para la máquina con Qwen)

Todo lo necesario está en el repo: el código, los datos y el archivo de referencia del guardián (`guard/artifacts/all-MiniLM-L6-v2.npz`, versión 1, decide solo con el ataque). No hace falta entrenar. Lo único que se descarga es el modelo de embeddings (MiniLM, ~90 MB, de Hugging Face, la primera vez) y, si se corre DeBERTa, su modelo.

## 1. Preparar

```sh
git pull                                    # master
uv venv && source .venv/bin/activate        # o python -m venv .venv
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -e ".[guard,bench]"
python -m pytest tests                      # adaptadores, sin modelo ni API
python -c "import guard; guard.warmup(); print(guard.describe())"   # descarga MiniLM y carga la referencia
```

`guard.describe()` tiene que decir `decision: solo ataque` y `tau_alto ≈ 0.9936`. Anotar el commit (`git rev-parse --short HEAD`): es la versión del guardián de todos los números.

## 2. El agente: Qwen 8B local

El runner usa el cliente de OpenAI, así que Qwen tiene que estar detrás de una API compatible y **con llamadas a herramientas**. Con Ollama:

```sh
ollama pull qwen3:8b
ollama serve                                 # http://localhost:11434
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=ollama                 # cualquier valor; el runner exige que exista
```

(Con vLLM: `--enable-auto-tool-choice` y el parser de herramientas de Qwen; `OPENAI_BASE_URL=http://localhost:8000/v1`.) `--modelo` es el nombre que da el servidor (`qwen3:8b`). Como AgentDojo no conoce ese modelo, el runner agrega `-local` al nombre del pipeline y el ataque se dirige a “Local model”. **Todas las defensas con el mismo modelo.**

## 3. Probar antes de lo largo

```sh
# sin LLM: solo comprueba que todo corre (escribe en runs/offline/, no son resultados)
python -m bench.run_agentdojo --offline -s banking -ut user_task_0 -it injection_task_0

# piloto con Qwen: 2 tareas × 2 inyecciones, todas las defensas
python -m bench.run_agentdojo --modelo qwen3:8b -s banking -ut user_task_0 -ut user_task_1 -it injection_task_0 -it injection_task_1
```

Mirar en la salida: que Qwen sí llame herramientas (utilidad sin defensa > 0) y cuántas salidas marca el guardián (`marcadas x/y`). Si marca salidas limpias de banca, es el problema conocido de `docs/data-banking-negatives.md`.

## 4. Las corridas que van a la ficha

```sh
python -m bench.run_agentdojo --modelo qwen3:8b -s banking --force-rerun
# después, si hay tiempo: -s workspace, -s slack, -s travel
```

Defensas por defecto: `none`, `keyword`, `transformers_pi_detector` (DeBERTa), `guard-detect`, `guard-sanitize`. Ataque por defecto: `important_instructions`.

## 5. Dónde quedan los números

- `results/<fecha>-<commit>-agentdojo-<suite>-<defensa>.json` y una línea por defensa en `results/summary.csv` (Contrato 4). **Se suben al repo:** son los números de la ficha.
- `runs/`: trazas completas de AgentDojo, no se versionan.
- Si se repite un comando sin `--force-rerun`, AgentDojo reutiliza casos y esos no suman latencias del guardián (el JSON lo dice).

## Reglas

- El guardián queda **congelado** en el commit anotado: no se cambia nada de `guard/` entre corridas. Si cambia, se anota y se dice en la ficha.
- El conjunto de prueba (`data/test.csv`, `data/mcp_test.jsonl`) se corre **una sola vez**, con el guardián congelado (`bench/eval_detector.py`, pendiente).
- Ningún texto de AgentDojo entra al entrenamiento ni a los umbrales.
