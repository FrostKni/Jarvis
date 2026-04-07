from typing import Dict, Any, Optional
from backend.memory.store import PersistentStore


class WorldModel:
    """User preferences, habits, and context."""

    def __init__(self, store: PersistentStore):
        self.store = store

    async def get_preference(self, key: str) -> Optional[str]:
        """Get user preference."""
        return await self.store.get_preference(key)

    async def set_preference(self, key: str, value: str):
        """Set user preference."""
        await self.store.set_preference(key, value)

    async def get_user_context(self) -> Dict[str, Any]:
        """Get full user context for LLM prompting."""
        prefs = await self.store.get_all_preferences()

        context_parts = []
        if prefs.get("location"):
            context_parts.append(f"User location: {prefs['location']}")
        if prefs.get("timezone"):
            context_parts.append(f"User timezone: {prefs['timezone']}")
        if prefs.get("name"):
            context_parts.append(f"User name: {prefs['name']}")

        return {
            "preferences": prefs,
            "context_text": "\n".join(context_parts) if context_parts else "",
        }

    async def infer_preference(self, action: str, params: dict):
        """Infer and store preferences from user actions."""
        if action == "check_weather" and "location" in params:
            current = await self.get_preference("location")
            if not current:
                await self.set_preference("location", params["location"])
