"""Combinación aprendida de los puntajes (docs/algorithm.md, "5. Decisión").

Una regresión logística sobre los percentiles ya calibrados: ataque, pedido, llamada y vecinos
(0 y una marca cuando falta la referencia) y la clase del trozo. Su salida es una sola
probabilidad, comparable entre clases y entre trozos con distinta cantidad de referencias:
reemplaza el máximo, 1 − m^k y los dos umbrales cuando gana en validación.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

CLASSES = ("path", "value-1", "value-23", "value-whole")
REFS = ("request", "tool", "peers")
FEATURES = (
    "bias",
    "attack_tail",  # −log(1 − p): estira la cola alta, donde está la diferencia
    *(f"p_{r}" for r in REFS),
    *(f"has_{r}" for r in REFS),
    *(f"class_{c}" for c in CLASSES),
)
L2 = 1.0


def features(
    classes: Sequence[str],
    attack_scores: Sequence[float],
    refs: Sequence[Mapping[str, float | None]],
) -> np.ndarray:
    """Una fila por trozo; `classes` sale de reference.chunk_class."""
    rows = []
    for cls, a, ps in zip(classes, attack_scores, refs, strict=True):
        rows.append(
            [
                1.0,
                -np.log(max(1.0 - a, 1e-12)),
                *((ps.get(r) or 0.0) for r in REFS),
                *(float(ps.get(r) is not None) for r in REFS),
                *(float(cls == k) for k in CLASSES),
            ]
        )
    return np.array(rows, dtype=np.float64).reshape(-1, len(FEATURES))


def fit(x: np.ndarray, y: np.ndarray, iterations: int = 50) -> np.ndarray:
    """Newton con L2 y clases equilibradas (ataques y legítimos pesan lo mismo)."""
    w = np.zeros(x.shape[1])
    weights = np.where(y == 1, 0.5 / max(1, y.sum()), 0.5 / max(1, (1 - y).sum()))
    reg = np.full(x.shape[1], L2 / len(y))
    reg[0] = 0.0  # sin penalizar el sesgo
    for _ in range(iterations):
        p = predict(x, w)
        grad = x.T @ (weights * (p - y)) + reg * w
        hess = (x * (weights * p * (1 - p))[:, None]).T @ x + np.diag(reg + 1e-9)
        step = np.linalg.solve(hess, grad)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w


def predict(x: np.ndarray, w: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x @ w, -50, 50)))
