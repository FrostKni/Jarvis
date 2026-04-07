import json
import re
from typing import List, Dict

from backend.brain.llm import LLMClient
from backend.memory.vector import VectorMemory
from backend.memory.world_model import WorldModel
from backend.memory.graph import GraphMemory


EXTRACTION_PROMPT = """Analyze this conversation and extract:
1. A brief summary (3-5 sentences)
2. Key facts about the user (preferences, events, habits)
3. Entities mentioned (people, places, projects)

Conversation:
{conversation}

Respond ONLY with valid JSON. No additional text before or after.
{{
  "summary": "...",
  "facts": [{{"type": "preference|event|habit", "content": "..."}}],
  "entities": [{{"name": "...", "type": "person|place|project", "context": "..."}}]
}}"""


class MemoryConsolidator:
    def __init__(
        self,
        llm: LLMClient,
        vector: VectorMemory,
        world_model: WorldModel,
        graph: GraphMemory,
    ):
        self.llm = llm
        self.vector = vector
        self.world_model = world_model
        self.graph = graph

    async def consolidate(self, session_id: str, turns: List[Dict]) -> Dict:
        if not turns:
            return {"status": "skipped", "reason": "no turns"}

        conversation = self._format_turns(turns)
        prompt = EXTRACTION_PROMPT.format(conversation=conversation)
        extraction = await self._extract(prompt)

        if extraction.get("summary"):
            self.vector.store(f"Session {session_id}: {extraction['summary']}")

        for fact in extraction.get("facts", []):
            if fact["type"] == "preference":
                await self._update_preference(fact["content"])

        for entity in extraction.get("entities", []):
            await self.graph.upsert_entity(
                entity["name"],
                entity["type"],
                entity.get("context", ""),
            )

        return {
            "status": "success",
            "summary": extraction.get("summary", ""),
            "facts_count": len(extraction.get("facts", [])),
            "entities_count": len(extraction.get("entities", [])),
        }

    def _format_turns(self, turns: List[Dict]) -> str:
        lines = []
        for turn in turns:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            lines.append(f"{role.capitalize()}: {content}")
        return "\n".join(lines)

    async def _extract(self, prompt: str) -> Dict:
        response = await self.llm.complete([{"role": "user", "content": prompt}])
        try:
            text = response
            json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
            if json_match:
                text = json_match.group(1)
            return json.loads(text.strip())
        except (json.JSONDecodeError, KeyError, IndexError, AttributeError):
            return {"summary": "", "facts": [], "entities": []}

    async def _update_preference(self, content: str):
        if ":" in content:
            parts = content.split(":", 1)
            if len(parts) == 2 and parts[0].strip():
                key, value = parts
                await self.world_model.set_preference(
                    key.strip().lower(), value.strip()
                )
