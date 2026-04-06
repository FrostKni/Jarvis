import asyncio
import json
from typing import AsyncGenerator
import anthropic
import httpx
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from backend.config import get_settings

settings = get_settings()

# Anthropic models
SONNET = "claude-sonnet-4-5"
HAIKU = "claude-haiku-4-5"

# Gemini models
GEMINI_PRO = "gemini-2.0-flash"
GEMINI_FAST = "gemini-2.0-flash-lite"


class LLMClient:
    def __init__(self):
        self._anthropic = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        genai.configure(api_key=settings.gemini_api_key)

    def _provider(self) -> str:
        if settings.local_mode:
            return "ollama"
        return settings.llm_provider

    async def complete(self, messages: list[dict], system: str = "", fast: bool = False) -> str:
        match self._provider():
            case "gemini":  return await self._gemini_complete(messages, system, fast)
            case "ollama":  return await self._ollama_complete(messages, system)
            case _:         return await self._anthropic_complete(messages, system, fast)

    async def stream(self, messages: list[dict], system: str = "", fast: bool = False) -> AsyncGenerator[str, None]:
        match self._provider():
            case "gemini":
                async for t in self._gemini_stream(messages, system, fast): yield t
            case "ollama":
                async for t in self._ollama_stream(messages, system): yield t
            case _:
                async for t in self._anthropic_stream(messages, system, fast): yield t

    async def complete_with_tools(self, messages: list[dict], tools: list[dict], system: str = "") -> dict:
        """Tool use — Anthropic and Gemini both supported; Ollama falls back to Anthropic."""
        if self._provider() == "gemini":
            return await self._gemini_complete_with_tools(messages, tools, system)
        response = await self._anthropic.messages.create(
            model=SONNET, max_tokens=4096, system=system, tools=tools, messages=messages,
        )
        return response

    # ── Anthropic ──────────────────────────────────────────────────────────────

    async def _anthropic_complete(self, messages: list[dict], system: str, fast: bool) -> str:
        model = HAIKU if fast else SONNET
        r = await self._anthropic.messages.create(
            model=model, max_tokens=1024, system=system, messages=messages,
        )
        return r.content[0].text

    async def _anthropic_stream(self, messages: list[dict], system: str, fast: bool) -> AsyncGenerator[str, None]:
        model = HAIKU if fast else SONNET
        async with self._anthropic.messages.stream(
            model=model, max_tokens=1024, system=system, messages=messages,
        ) as s:
            async for text in s.text_stream:
                yield text

    # ── Gemini ─────────────────────────────────────────────────────────────────

    def _gemini_model(self, fast: bool, system: str):
        return genai.GenerativeModel(
            model_name=GEMINI_FAST if fast else GEMINI_PRO,
            system_instruction=system or None,
            generation_config=GenerationConfig(max_output_tokens=1024),
        )

    @staticmethod
    def _to_gemini_history(messages: list[dict]) -> tuple[list, str]:
        """Split messages into history (all but last) and the final user prompt."""
        history = []
        for m in messages[:-1]:
            role = "user" if m["role"] == "user" else "model"
            history.append({"role": role, "parts": [m["content"]]})
        last = messages[-1]["content"] if messages else ""
        return history, last

    async def _gemini_complete(self, messages: list[dict], system: str, fast: bool) -> str:
        model = self._gemini_model(fast, system)
        history, prompt = self._to_gemini_history(messages)
        chat = model.start_chat(history=history)
        response = await asyncio.to_thread(chat.send_message, prompt)
        return response.text

    async def _gemini_stream(self, messages: list[dict], system: str, fast: bool) -> AsyncGenerator[str, None]:
        model = self._gemini_model(fast, system)
        history, prompt = self._to_gemini_history(messages)
        chat = model.start_chat(history=history)

        def _send():
            return chat.send_message(prompt, stream=True)

        response = await asyncio.to_thread(_send)
        for chunk in response:
            if chunk.text:
                yield chunk.text

    async def _gemini_complete_with_tools(self, messages: list[dict], tools: list[dict], system: str) -> object:
        """Translate Anthropic-style tool schema → Gemini function declarations."""
        from google.generativeai.types import FunctionDeclaration, Tool as GeminiTool

        fn_decls = [
            FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=t["input_schema"],
            )
            for t in tools
        ]
        model = genai.GenerativeModel(
            model_name=GEMINI_PRO,
            system_instruction=system or None,
            tools=[GeminiTool(function_declarations=fn_decls)],
        )
        history, prompt = self._to_gemini_history(messages)
        chat = model.start_chat(history=history)
        response = await asyncio.to_thread(chat.send_message, prompt)
        return _GeminiToolResponse(response)

    # ── Ollama ─────────────────────────────────────────────────────────────────

    async def _ollama_complete(self, messages: list[dict], system: str) -> str:
        payload = {
            "model": "qwen2.5:7b",
            "messages": [{"role": "system", "content": system}] + messages if system else messages,
            "stream": False,
        }
        async with httpx.AsyncClient(base_url=settings.ollama_base_url) as client:
            r = await client.post("/api/chat", json=payload, timeout=60)
            return r.json()["message"]["content"]

    async def _ollama_stream(self, messages: list[dict], system: str) -> AsyncGenerator[str, None]:
        payload = {
            "model": "qwen2.5:7b",
            "messages": [{"role": "system", "content": system}] + messages if system else messages,
            "stream": True,
        }
        async with httpx.AsyncClient(base_url=settings.ollama_base_url) as client:
            async with client.stream("POST", "/api/chat", json=payload, timeout=60) as r:
                async for line in r.aiter_lines():
                    if line:
                        data = json.loads(line)
                        if token := data.get("message", {}).get("content", ""):
                            yield token


class _GeminiToolResponse:
    """Wraps a Gemini response to match the Anthropic response interface used by the orchestrator."""

    def __init__(self, response):
        self._response = response
        parts = response.candidates[0].content.parts if response.candidates else []
        self.content = []
        self.stop_reason = "end_turn"

        for part in parts:
            if fn := getattr(part, "function_call", None):
                self.stop_reason = "tool_use"
                self.content.append(_GeminiFunctionCall(fn))
            elif txt := getattr(part, "text", None):
                self.content.append(_GeminiText(txt))


class _GeminiFunctionCall:
    type = "tool_use"

    def __init__(self, fn):
        self.id = f"gemini_{fn.name}"
        self.name = fn.name
        self.input = dict(fn.args)


class _GeminiText:
    type = "text"

    def __init__(self, text: str):
        self.text = text
