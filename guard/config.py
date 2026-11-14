"""Toda la configuración del guardián en un solo lugar (modelo, trozos, rutas).

Los umbrales no van aquí: los elige `python -m guard.train` en validación y quedan
congelados en `guard/artifacts/<modelo>.json` junto con la dirección de ataque.
"""

from __future__ import annotations

import os
from pathlib import Path

RETIRADO = "[contenido retirado por el guardián]"
ORIGENES = ("herramienta", "manifiesto", "usuario")

# Modelo de embeddings. Se cambia con la variable de entorno GUARD_MODEL.
#   "minilm" -> sentence-transformers/all-MiniLM-L6-v2 (transformer, ~0,2-0,8 s por salida en un portátil)
#   "potion" -> minishlab/potion-base-8M (embeddings estáticos, ~5 ms por salida)
MODELOS = {
    "minilm": ("sentence-transformers", "sentence-transformers/all-MiniLM-L6-v2"),
    "potion": ("model2vec", "minishlab/potion-base-8M"),
}
MODELO = os.environ.get("GUARD_MODEL", "minilm")

# Trozos
VENTANAS = (1, 2, 3)          # oraciones por ventana
MIN_PALABRAS = 4              # ventanas más cortas se ignoran
MAX_PALABRAS_ORACION = 60     # oraciones más largas (JSON, listas) se parten
MAX_PALABRAS_TEXTO_CORTO = 120  # hasta aquí el texto completo también es un trozo

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data"
ARTEFACTOS = Path(__file__).resolve().parent / "artifacts"


def ruta_artefacto(modelo: str = MODELO) -> Path:
    return ARTEFACTOS / f"{modelo}.json"
