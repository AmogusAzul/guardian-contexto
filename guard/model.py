"""Pasos 3 a 5 de docs/algorithm.md: centrar, attack_score y drift_score.

Los parámetros (promedio del corpus, dirección de ataque, escala y umbrales) se
ajustan con `python -m guard.train` y se guardan en un JSON en guard/artifacts/.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from guard import config


def _unit(v: np.ndarray) -> np.ndarray:
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


@dataclass
class Parametros:
    modelo: str
    promedio: list[float]       # embedding promedio del corpus de entrenamiento (paso 3)
    direccion: list[float]      # promedio(ataques) - promedio(legítimos), centrada y normalizada (paso 4)
    escala_min: float           # coseno crudo que se vuelve attack_score = 0
    escala_max: float           # coseno crudo que se vuelve attack_score = 1
    tau_alto: float             # attack_score >= tau_alto -> se marca
    tau_bajo: float             # attack_score >= tau_bajo y drift_score >= tau_drift -> se marca
    tau_drift: float
    notas: dict                 # de dónde salió (datos, n, métricas de validación)

    # --- cálculo -------------------------------------------------------------
    def centrar(self, v: np.ndarray) -> np.ndarray:
        return _unit(v - np.asarray(self.promedio, dtype=np.float32))

    def coseno_ataque(self, v_centrado: np.ndarray) -> np.ndarray:
        return v_centrado @ np.asarray(self.direccion, dtype=np.float32)

    def attack_score(self, v_centrado: np.ndarray) -> np.ndarray:
        return self.escalar(self.coseno_ataque(v_centrado))

    def escalar(self, crudo: np.ndarray) -> np.ndarray:
        """Coseno crudo -> attack_score en [0, 1]."""
        return np.clip((crudo - self.escala_min) / max(self.escala_max - self.escala_min, 1e-6), 0.0, 1.0)

    @staticmethod
    def drift_score(v_centrado: np.ndarray, tarea_centrada: np.ndarray) -> np.ndarray:
        return np.clip(1.0 - v_centrado @ tarea_centrada, 0.0, 1.0)

    def marcar(self, attack: float, drift: float | None) -> bool:
        if attack >= self.tau_alto:
            return True
        return drift is not None and attack >= self.tau_bajo and drift >= self.tau_drift

    # --- disco -----------------------------------------------------------------
    def guardar(self, ruta: Path | None = None) -> Path:
        ruta = ruta or config.ruta_artefacto(self.modelo)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return ruta


@lru_cache(maxsize=None)
def cargar(modelo: str = config.MODELO) -> Parametros:
    ruta = config.ruta_artefacto(modelo)
    if not ruta.exists():
        raise FileNotFoundError(f"No hay {ruta}. Correr: python -m guard.train  (o GUARD_MODEL=<otro>)")
    return Parametros(**json.loads(ruta.read_text(encoding="utf-8")))


def ajustar(modelo: str, v_ataques: np.ndarray, v_legitimos: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (promedio, dirección) a partir de embeddings normalizados."""
    promedio = np.vstack([v_ataques, v_legitimos]).mean(axis=0)
    ca, cl = _unit(v_ataques - promedio), _unit(v_legitimos - promedio)
    return promedio, _unit(ca.mean(axis=0) - cl.mean(axis=0))
