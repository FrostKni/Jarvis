from backend.memory.vector import VectorMemory
from backend.memory.graph import GraphMemory
from backend.memory.store import PersistentStore
import re


class MemoryAssembler:
    def __init__(self, vector: VectorMemory, graph: GraphMemory, store: PersistentStore):
        self.vector = vector
        self.graph = graph
        self.store = store

    async def build_context(self, query: str) -> str:
        # Run vector search and preferences in parallel
        import asyncio
        memories, prefs = await asyncio.gather(
            asyncio.to_thread(self.vector.search, query, 5),
            self.store.get_all_preferences(),
        )

        # Extract entity names from query for graph lookup
        entities = _extract_names(query)
        graph_ctx = await self.graph.get_context_for(entities)

        parts = []
        if prefs:
            parts.append("User preferences:\n" + "\n".join(f"- {k}: {v}" for k, v in prefs.items()))
        if memories:
            parts.append("Relevant memories:\n" + "\n".join(f"- {m}" for m in memories))
        if graph_ctx:
            parts.append("Known relationships:\n" + graph_ctx)

        return "\n\n".join(parts)


def _extract_names(text: str) -> list[str]:
    # Simple capitalized word extraction as entity hint
    return list(set(re.findall(r'\b[A-Z][a-z]+\b', text)))
