"""Guardián de contexto: revisa las salidas de herramientas antes de que entren al contexto del LLM.

GUARD_MOCK=1 usa el mock de palabras clave (sin dependencias) en vez del guardián real.
"""

import os

if os.environ.get("GUARD_MOCK") == "1":
    from guard.mock import check
else:
    from guard.check import check

__all__ = ["check"]
