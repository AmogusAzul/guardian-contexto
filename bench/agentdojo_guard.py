"""Contrato 2 (docs/architecture.md): el guardián como defensa de AgentDojo.

Las dos defensas heredan de `PromptInjectionDetector` de AgentDojo, que ya recorre los
mensajes de herramienta del final de la conversación, llama `detect(texto)` en cada uno y,
si devuelve True, reemplaza el contenido con `transform(contenido)`.

- `GuardDetect` (guard-detect): usa el `transform` de AgentDojo, que descarta la salida
  completa ("<Data omitted because a prompt injection was detected>"), igual que DeBERTa.
- `GuardSanitize` (guard-sanitize): sobrescribe `transform` para devolver `texto_limpio`.

Las dos llaman `check()` con la MISMA tarea (primer mensaje del usuario), así que la única
diferencia entre ambas es descartar frente a sanear.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence

from agentdojo.agent_pipeline import PromptInjectionDetector
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionsRuntime
from agentdojo.types import ChatMessage, MessageContentBlock, get_text_content_as_str, text_content_block_from_string

import guard

CheckFn = Callable[..., tuple[bool, dict]]


def tarea_de(messages: Sequence[ChatMessage], query: str | None = None) -> str | None:
    """La tarea del usuario: el primer mensaje con role 'user' (o `query` si no hay ninguno)."""
    for m in messages:
        if m["role"] == "user":
            return get_text_content_as_str(m["content"] or []) or query
    return query


class GuardDetect(PromptInjectionDetector):
    """guard-detect: si `check()` marca algo, AgentDojo descarta la salida completa."""

    nombre = "guard-detect"

    def __init__(self, check_fn: CheckFn | None = None) -> None:
        # "message": revisa cada salida de herramienta por separado (como DeBERTa en AgentDojo).
        super().__init__(mode="message", raise_on_injection=False)
        self._check = check_fn or guard.check
        self.tarea: str | None = None
        self.registro: list[dict] = []  # una fila por salida de herramienta revisada
        self._ultimo: dict | None = None

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = {},
    ) -> tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        # detect() solo recibe el texto: la tarea se fija aquí, antes de que el padre lo llame.
        self.tarea = tarea_de(messages, query)
        return super().query(query, runtime, env, messages, extra_args)

    def detect(self, tool_output: str) -> tuple[bool, float]:
        try:
            permitido, info = self._check(tool_output, tarea=self.tarea, origen="herramienta")
        except NotImplementedError:
            from guard.mock import check as mock_check
            self._check = mock_check
            permitido, info = self._check(tool_output, tarea=self.tarea, origen="herramienta")

        self._ultimo = info
        self.registro.append(
            {
                "defensa": self.nombre,
                "permitido": permitido,
                "attack_score": info["attack_score"],
                "drift_score": info["drift_score"],
                "latencia_ms": info["latencia_ms"],
                "n_caracteres": len(tool_output),
                "trozos_marcados": info["trozos_marcados"],
            }
        )
        return (not permitido), float(info["attack_score"])


class GuardSanitize(GuardDetect):
    """guard-sanitize: en vez de descartar, deja la salida con los trozos marcados retirados."""

    nombre = "guard-sanitize"

    def transform(self, tool_output: list[MessageContentBlock]) -> list[MessageContentBlock]:
        # El padre llama transform() justo después de detect() sobre el mismo mensaje.
        assert self._ultimo is not None, "transform() sin detect() previo"
        limpio = self._ultimo["texto_limpio"]
        otros = [b for b in tool_output if b["type"] != "text"]
        return [text_content_block_from_string(limpio), *otros]
