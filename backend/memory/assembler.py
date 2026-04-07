from backend.memory.vector import VectorMemory
from backend.memory.graph import GraphMemory
from backend.memory.store import PersistentStore
from backend.memory.procedural import ProceduralMemory
from backend.memory.world_model import WorldModel
import asyncio
import re


class MemoryAssembler:
    def __init__(
        self,
        vector: VectorMemory,
        graph: GraphMemory,
        store: PersistentStore,
        procedural: ProceduralMemory = None,
        world_model: WorldModel = None,
    ):
        self.vector = vector
        self.graph = graph
        self.store = store
        self.procedural = procedural
        self.world_model = world_model

    async def build_context(self, query: str) -> str:
        tasks = [
            asyncio.to_thread(self.vector.search, query, 5),
        ]

        if self.world_model:
            tasks.append(self.world_model.get_user_context())
        else:
            tasks.append(self._fallback_user_context())

        results = await asyncio.gather(*tasks)
        memories = results[0]
        user_context = results[1]

        entities = _extract_names(query)
        graph_ctx = await self.graph.get_context_for(entities)

        parts = []
        prefs = user_context.get("preferences", {})
        if prefs:
            parts.append(
                "User preferences:\n"
                + "\n".join(f"- {k}: {v}" for k, v in prefs.items())
            )
        if memories:
            parts.append("Relevant memories:\n" + "\n".join(f"- {m}" for m in memories))
        if graph_ctx:
            parts.append("Known relationships:\n" + graph_ctx)

        if self.procedural:
            suggestions = await self.procedural.suggest_actions()
            if suggestions:
                suggestion_text = "Common actions:\n" + "\n".join(
                    f"- {s['action']} (confidence: {s['confidence']:.0%})"
                    for s in suggestions[:3]
                )
                parts.append(suggestion_text)

        return "\n\n".join(parts)

    async def _fallback_user_context(self) -> dict:
        prefs = await self.store.get_all_preferences()
        return {"preferences": prefs, "context_text": ""}


def _extract_names(text: str) -> list[str]:
    # Simple capitalized word extraction as entity hint
    return list(set(re.findall(r"\b[A-Z][a-z]+\b", text)))
