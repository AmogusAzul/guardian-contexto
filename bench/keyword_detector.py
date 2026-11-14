"""Línea base de palabras clave: "lo que cualquiera haría en una tarde" (docs/evaluation.md).

Frases típicas de inyección de listas públicas y del sentido común. A propósito NO incluye
marcas propias de la plantilla de AgentDojo ("<INFORMATION>", "important message from me"):
sería ajustar la línea base al examen final.

Como en AgentDojo es un `PromptInjectionDetector`, cuando detecta algo se descarta la
salida completa (igual que guard-detect y DeBERTa).
"""

from __future__ import annotations

import re

from agentdojo.agent_pipeline import PromptInjectionDetector

PATRONES = [
    r"\bignore (all |any |the )?(previous|prior|above|earlier) (instructions|messages|prompts?)",
    r"\bdisregard (all |any |the )?(previous|prior|above|earlier|user'?s?) ",
    r"\bforget (everything|all|what|your) ",
    r"\bnew (instructions|system prompt|task|objective)\b",
    r"\bsystem (prompt|override|message)\b",
    r"\byou are now\b",
    r"\b(assistant|ai|llm|language model|agent)\s*[:,]",
    r"\bdo not (tell|inform|mention|notify) (the user|anyone)\b",
    r"\binstead of (what|the task) the user\b",
    r"\bignora (todas )?(las )?instrucciones",
]
_RE = re.compile("|".join(f"(?:{p})" for p in PATRONES), re.IGNORECASE)


def tiene_palabras_clave(texto: str) -> bool:
    return _RE.search(texto) is not None


class KeywordDetector(PromptInjectionDetector):
    nombre = "keyword"

    def __init__(self) -> None:
        super().__init__(mode="message", raise_on_injection=False)
        self.registro: list[dict] = []

    def detect(self, tool_output: str) -> bool:
        marcado = tiene_palabras_clave(tool_output)
        self.registro.append({"defensa": self.nombre, "permitido": not marcado})
        return marcado
