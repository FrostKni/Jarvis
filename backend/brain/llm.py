import asyncio
import json
from typing import AsyncGenerator
from dataclasses import dataclass, asdict
import anthropic
import httpx
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from backend.config import get_settings
from openai import AsyncOpenAI
import ssl

settings = get_settings()

SONNET = "claude-sonnet-4-5"
HAIKU = "claude-haiku-4-5"
GEMINI_PRO = "gemini-2.0-flash"
GEMINI_FAST = "gemini-2.0-flash-lite"


class LLMClient:
    def __init__(self):
        self._anthropic = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        genai.configure(api_key=settings.gemini_api_key)
        self._openai_compatible = None
        if settings.openai_compatible_base_url:
            http_client = httpx.AsyncClient(verify=False)
            self._openai_compatible = AsyncOpenAI(
                base_url=settings.openai_compatible_base_url,
                api_key=settings.openai_compatible_api_key or "none",
                http_client=http_client,
            )

    def _provider(self) -> str:
        if settings.openai_compatible_base_url:
            return "openai_compatible"
        if settings.local_mode:
            return "ollama"
        return settings.llm_provider

    async def complete(
        self, messages: list[dict], system: str = "", fast: bool = False
    ) -> str:
        match self._provider():
            case "gemini":
                return await self._gemini_complete(messages, system, fast)
            case "ollama":
                return await self._ollama_complete(messages, system)
            case "openai_compatible":
                return await self._openai_compatible_complete(messages, system, fast)
            case _:
                return await self._anthropic_complete(messages, system, fast)

    async def stream(
        self, messages: list[dict], system: str = "", fast: bool = False
    ) -> AsyncGenerator[str, None]:
        match self._provider():
            case "gemini":
                async for t in self._gemini_stream(messages, system, fast):
                    yield t
            case "ollama":
                async for t in self._ollama_stream(messages, system):
                    yield t
            case "openai_compatible":
                async for t in self._openai_compatible_stream(messages, system, fast):
                    yield t
            case _:
                async for t in self._anthropic_stream(messages, system, fast):
                    yield t

    async def complete_with_tools(
        self, messages: list[dict], tools: list[dict], system: str = ""
    ) -> dict:
        if self._provider() == "gemini":
            return await self._gemini_complete_with_tools(messages, tools, system)
        if self._provider() == "openai_compatible":
            return await self._openai_compatible_complete_with_tools(
                messages, tools, system
            )
        response = await self._anthropic.messages.create(
            model=SONNET, max_tokens=4096, system=system, tools=tools, messages=messages
        )
        return response

    async def _anthropic_complete(
        self, messages: list[dict], system: str, fast: bool
    ) -> str:
        model = HAIKU if fast else SONNET
        r = await self._anthropic.messages.create(
            model=model, max_tokens=1024, system=system, messages=messages
        )
        return r.content[0].text

    async def _anthropic_stream(
        self, messages: list[dict], system: str, fast: bool
    ) -> AsyncGenerator[str, None]:
        model = HAIKU if fast else SONNET
        async with self._anthropic.messages.stream(
            model=model, max_tokens=1024, system=system, messages=messages
        ) as s:
            async for text in s.text_stream:
                yield text

    def _gemini_model(self, fast: bool, system: str):
        return genai.GenerativeModel(
            model_name=GEMINI_FAST if fast else GEMINI_PRO,
            system_instruction=system or None,
            generation_config=GenerationConfig(max_output_tokens=1024),
        )

    @staticmethod
    def _to_gemini_history(messages: list[dict]) -> tuple[list, str]:
        history = []
        for m in messages[:-1]:
            role = "user" if m["role"] == "user" else "model"
            history.append({"role": role, "parts": [m["content"]]})
        last = messages[-1]["content"] if messages else ""
        return history, last

    async def _gemini_complete(
        self, messages: list[dict], system: str, fast: bool
    ) -> str:
        model = self._gemini_model(fast, system)
        history, prompt = self._to_gemini_history(messages)
        chat = model.start_chat(history=history)
        response = await asyncio.to_thread(chat.send_message, prompt)
        return response.text

    async def _gemini_stream(
        self, messages: list[dict], system: str, fast: bool
    ) -> AsyncGenerator[str, None]:
        model = self._gemini_model(fast, system)
        history, prompt = self._to_gemini_history(messages)
        chat = model.start_chat(history=history)

        def _send():
            return chat.send_message(prompt, stream=True)

        response = await asyncio.to_thread(_send)
        for chunk in response:
            if chunk.text:
                yield chunk.text

    async def _gemini_complete_with_tools(
        self, messages: list[dict], tools: list[dict], system: str
    ) -> object:
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

    async def _ollama_complete(self, messages: list[dict], system: str) -> str:
        payload = {
            "model": "qwen2.5:7b",
            "messages": [{"role": "system", "content": system}] + messages
            if system
            else messages,
            "stream": False,
        }
        async with httpx.AsyncClient(base_url=settings.ollama_base_url) as client:
            r = await client.post("/api/chat", json=payload, timeout=60)
            return r.json()["message"]["content"]

    async def _ollama_stream(
        self, messages: list[dict], system: str
    ) -> AsyncGenerator[str, None]:
        payload = {
            "model": "qwen2.5:7b",
            "messages": [{"role": "system", "content": system}] + messages
            if system
            else messages,
            "stream": True,
        }
        async with httpx.AsyncClient(base_url=settings.ollama_base_url) as client:
            async with client.stream(
                "POST", "/api/chat", json=payload, timeout=60
            ) as r:
                async for line in r.aiter_lines():
                    if line:
                        data = json.loads(line)
                        if token := data.get("message", {}).get("content", ""):
                            yield token

    async def _openai_compatible_complete(
        self, messages: list[dict], system: str, fast: bool
    ) -> str:
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        model = settings.openai_compatible_model or "gpt-4"
        response = await self._openai_compatible.chat.completions.create(
            model=model,
            messages=all_messages,
            max_tokens=1024,
        )
        return response.choices[0].message.content or ""

    async def _openai_compatible_stream(
        self, messages: list[dict], system: str, fast: bool
    ) -> AsyncGenerator[str, None]:
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        model = settings.openai_compatible_model or "gpt-4"
        stream = await self._openai_compatible.chat.completions.create(
            model=model,
            messages=all_messages,
            max_tokens=1024,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _openai_compatible_complete_with_tools(
        self, messages: list[dict], tools: list[dict], system: str
    ) -> dict:
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]

        model = settings.openai_compatible_model or "gpt-4"
        response = await self._openai_compatible.chat.completions.create(
            model=model,
            messages=all_messages,
            tools=openai_tools,
            max_tokens=4096,
        )
        return _OpenAICompatibleToolResponse(response)


class _GeminiToolResponse:
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

    def model_dump(self):
        return {
            "type": self.type,
            "id": self.id,
            "name": self.name,
            "input": self.input,
        }


class _GeminiText:
    type = "text"

    def __init__(self, text: str):
        self.text = text

    def model_dump(self):
        return {
            "type": self.type,
            "text": self.text,
        }


class _OpenAICompatibleToolResponse:
    def __init__(self, response):
        self._response = response
        self.content = []
        self.stop_reason = "end_turn"

        choice = response.choices[0]
        message = choice.message

        if message.tool_calls:
            self.stop_reason = "tool_use"
            for tc in message.tool_calls:
                self.content.append(_OpenAICompatibleToolCall(tc))
        elif message.content:
            self.content.append(_OpenAICompatibleText(message.content))

    def model_dump(self):
        return {
            "content": [c.model_dump() for c in self.content],
            "stop_reason": self.stop_reason,
        }

    def get_tool_calls_openai_format(self):
        """Get tool calls in OpenAI format for message construction"""
        return [c.to_openai_format() for c in self.content if c.type == "tool_use"]


class _OpenAICompatibleToolCall:
    type = "tool_use"

    def __init__(self, tool_call):
        self.id = tool_call.id
        self.name = tool_call.function.name
        self.input = json.loads(tool_call.function.arguments)

    def model_dump(self):
        """Anthropic-compatible format"""
        return {
            "type": self.type,
            "id": self.id,
            "name": self.name,
            "input": self.input,
        }

    def to_openai_format(self):
        """OpenAI-native format for message construction"""
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": json.dumps(self.input)},
        }


class _OpenAICompatibleText:
    type = "text"

    def __init__(self, text: str):
        self.text = text

    def model_dump(self):
        return {
            "type": self.type,
            "text": self.text,
        }
