"""GoogleLLM de AgentDojo 0.1.35 arreglado para Gemini 3 (thought signatures).

Gemini 3 devuelve una `thought_signature` en cada paso con llamadas a herramientas y exige
recibirla de vuelta en el historial; si falta responde 400 "Function call is missing a
thought_signature". AgentDojo convierte la respuesta a su `FunctionCall` y la firma se pierde.

Esta subclase guarda la firma de cada llamada (indexada por el id de la llamada) y la vuelve
a poner al reconstruir el historial. Si falta (no debería), usa el valor comodín que Google
documenta para llamadas que no generó el modelo. Lo demás es igual que en AgentDojo.
Docs: https://ai.google.dev/gemini-api/docs/thought-signatures
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence

from agentdojo.agent_pipeline.llms import google_llm as g
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionsRuntime
from agentdojo.types import ChatAssistantMessage, ChatMessage
from google.genai import types as genai_types

FIRMA_COMODIN = b"skip_thought_signature_validator"


class GeminiLLM(g.GoogleLLM):
    def __init__(self, model: str, client, temperature: float | None = 0.0, max_tokens: int = 65535) -> None:
        super().__init__(model, client, temperature=temperature, max_tokens=max_tokens)
        self._firmas: dict[str, bytes] = {}
        self._ids = itertools.count()
        self.firmas_comodin = 0  # cuántas veces faltó la firma real (para el registro)

    def _asistente_a_google(self, m: ChatAssistantMessage) -> genai_types.Content:
        parts = [genai_types.Part.from_text(text=b["content"]) for b in (m["content"] or []) if b["content"]]
        for i, tc in enumerate(m["tool_calls"] or []):
            p = genai_types.Part.from_function_call(name=tc.function, args=dict(tc.args))
            firma = self._firmas.get(tc.id or "")
            if firma is None and i == 0:  # Gemini 3 exige firma en la primera llamada de cada paso
                firma = FIRMA_COMODIN
                self.firmas_comodin += 1
            if firma is not None:
                p.thought_signature = firma
            parts.append(p)
        return genai_types.Content(role="model", parts=parts)

    def _a_google(self, m: ChatMessage) -> genai_types.Content:
        return self._asistente_a_google(m) if m["role"] == "assistant" else g._message_to_google(m)

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = {},
    ) -> tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        # Igual que GoogleLLM.query, salvo la conversión de mensajes del asistente.
        first_message, *other_messages = messages
        if first_message["role"] == "system":
            system_instruction = first_message["content"][0]["content"]
        else:
            system_instruction = None
            other_messages = messages
        google_messages = g._merge_tool_result_messages([self._a_google(m) for m in other_messages])
        google_functions = [g._function_to_google(tool) for tool in runtime.functions.values()]
        google_tools = [genai_types.Tool(function_declarations=google_functions)] if google_functions else None
        config = genai_types.GenerateContentConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
            tools=google_tools,
            system_instruction=system_instruction,
        )
        completion = g.chat_completion_request(self.model, self.client, google_messages, generation_config=config)
        output = g._google_to_assistant_message(completion)

        # Guardar la firma de cada llamada, con un id propio si Gemini no dio uno.
        cand = completion.candidates[0].content if completion.candidates else None
        partes_fc = [p for p in ((cand.parts if cand else None) or []) if p.function_call]
        for tc, p in zip(output["tool_calls"] or [], partes_fc):
            if not tc.id:
                tc.id = f"gemini-{next(self._ids)}"
            if p.thought_signature:
                self._firmas[tc.id] = p.thought_signature
        return query, runtime, env, [*messages, output], extra_args
