"""Datos de referencia congelados: promedio, dirección de ataque, tablas de percentiles y umbrales.

Los arma `python -m guard.train` (docs/algorithm.md, "Datos de referencia" y "Escalas") y se
guardan en guard/artifacts/<modelo>.npz. Aquí solo se cargan y se consultan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from guard.chunking import Chunk

ARTIFACTS = Path(__file__).parent / "artifacts"
QUANTILES = np.linspace(0.0, 1.0, 101)  # 101 puntos por tabla
TAIL = 0.95  # desde aquí la cola alta se extrapola (no se satura en 1)
MIN_TABLE = 200  # una clase con menos ejemplos usa la tabla de su tipo

# Umbrales provisionales hasta la búsqueda en validación (guard.train los reemplaza).
DEFAULT_THRESHOLDS = {"tau_high": 0.995, "tau_low": 0.95, "tau_drift": 0.95}


def chunk_class(c: Chunk) -> str:
    """Clase para las tablas: tipo y tamaño (1 oración, 2–3, valor o bloque entero)."""
    if c.kind == "path":
        return "path"
    return {1: "value-1", 2: "value-23", 3: "value-23"}.get(c.size, "value-whole")


def table(values: np.ndarray) -> np.ndarray:
    """Los 101 percentiles de unos cosenos crudos."""
    return np.quantile(np.asarray(values, dtype=np.float64), QUANTILES)


@dataclass
class Reference:
    model: str
    mean: np.ndarray  # para centrar
    direction: np.ndarray  # dirección de ataque, normalizada
    tables: dict[str, np.ndarray]  # "<puntaje>/<clase>" -> 101 percentiles de legítimos
    thresholds: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_THRESHOLDS)
    )
    data: str = ""  # de qué datos y commit salió

    def percentile(self, score: str, cls: str, raw: float) -> float | None:
        """Posición de `raw` entre los legítimos de su clase (0–1); None si no hay tabla.

        Entre puntos se interpola. Por encima del percentil 95 se usa una cola exponencial
        ajustada con los percentiles 95 y 99: un valor más alto que todos los legítimos de
        entrenamiento no se aplasta en 1, sigue ordenado (0,999, 0,9999…). Por debajo, 0.
        """
        t = self.tables.get(f"{score}/{cls}")
        if t is None:
            t = self.tables.get(f"{score}/{cls.split('-')[0]}")  # la tabla del tipo
        if t is None:
            return None
        q95, q99 = (
            float(np.interp(TAIL, QUANTILES, t)),
            float(np.interp(0.99, QUANTILES, t)),
        )
        if raw > q95 and q99 > q95:
            scale = (q99 - q95) / np.log(
                (1 - TAIL) / 0.01
            )  # exponencial que pasa por q95 y q99
            return float(1 - (1 - TAIL) * np.exp(-(raw - q95) / scale))
        return float(np.interp(raw, t, QUANTILES))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        arrays: dict[str, Any] = {
            "model": self.model,
            "mean": self.mean,
            "direction": self.direction,
            "data": self.data,
            "thresholds": np.array([self.thresholds[k] for k in DEFAULT_THRESHOLDS]),
        }
        arrays |= {f"table:{k}": v for k, v in self.tables.items()}
        np.savez(path, **arrays)

    @classmethod
    def load(cls, path: Path) -> Reference:
        z = np.load(path)
        return cls(
            model=str(z["model"]),
            mean=z["mean"],
            direction=z["direction"],
            tables={
                k.removeprefix("table:"): z[k]
                for k in z.files
                if k.startswith("table:")
            },
            thresholds=dict(
                zip(DEFAULT_THRESHOLDS, map(float, z["thresholds"]), strict=True)
            ),
            data=str(z["data"]),
        )


def artifact_path(model: str) -> Path:
    return ARTIFACTS / f"{model.rsplit('/', 1)[-1]}.npz"


@lru_cache(maxsize=4)
def load(model: str) -> Reference:
    path = artifact_path(model)
    if not path.exists():
        raise FileNotFoundError(
            f"faltan los datos de referencia {path}: correr `python -m guard.train`"
        )
    return Reference.load(path)
