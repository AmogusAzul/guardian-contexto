"""La llamada que produjo una salida (argumento `herramienta` de check()). Sin dependencias."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    """La llamada que produjo la salida: una de las referencias del desvío."""

    name: str
    description: str = ""
    arguments: Mapping[str, Any] = field(default_factory=dict)
