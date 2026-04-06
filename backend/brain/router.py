import json
from backend.brain.llm import LLMClient

ROUTER_SYSTEM = """You are an intent classifier for Jarvis AI assistant.
Given a user message, return JSON with:
- "intent": one of [chat, search, calendar, email, os_control, code, smart_home, weather, finance, music, vision, reminder, travel, health]
- "complexity": "fast" or "complex"
- "needs_tools": true/false
- "private": true/false (sensitive data, use local LLM)

Respond ONLY with valid JSON, no explanation."""


class IntentRouter:
    def __init__(self):
        self._llm = LLMClient()

    async def route(self, text: str) -> dict:
        response = await self._llm.complete(
            messages=[{"role": "user", "content": text}],
            system=ROUTER_SYSTEM,
            fast=True,
        )
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"intent": "chat", "complexity": "fast", "needs_tools": False, "private": False}
