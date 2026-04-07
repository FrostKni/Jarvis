import json
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, List, Optional
from backend.memory.store import PersistentStore


class ProceduralMemory:
    """Learn and recall user patterns/habits."""

    def __init__(self, store: PersistentStore = None):
        self.store = store
        self.patterns: Dict[str, dict] = defaultdict(
            lambda: {
                "frequency": 0,
                "params": {},
                "timestamps": [],
            }
        )

    async def record_action(
        self, action: str, params: dict, timestamp: datetime = None
    ):
        """Record a user action pattern."""
        timestamp = timestamp or datetime.now(timezone.utc)

        pattern = self.patterns[action]
        pattern["frequency"] += 1
        pattern["timestamps"].append(timestamp.isoformat())

        param_key = json.dumps(params, sort_keys=True)
        if "param_counts" not in pattern:
            pattern["param_counts"] = defaultdict(int)
        pattern["param_counts"][param_key] += 1

        max_count = max(pattern["param_counts"].values())
        for pk, count in pattern["param_counts"].items():
            if count == max_count:
                pattern["params"] = json.loads(pk)
                break

        if self.store:
            await self.store.log_task(action, json.dumps(params), "procedural_memory")

    async def get_pattern(self, action: str) -> Optional[dict]:
        """Get learned pattern for an action."""
        pattern = self.patterns.get(action)
        if not pattern or pattern["frequency"] < 3:
            return None

        return {
            "action": action,
            "frequency": pattern["frequency"],
            "params": pattern["params"],
            "last_occurred": pattern["timestamps"][-1]
            if pattern["timestamps"]
            else None,
        }

    async def suggest_actions(self, context: dict = None) -> List[dict]:
        """Suggest actions based on patterns and context."""
        suggestions = []

        for action, pattern in self.patterns.items():
            if pattern["frequency"] >= 3:
                suggestions.append(
                    {
                        "action": action,
                        "confidence": min(pattern["frequency"] / 10.0, 1.0),
                        "params": pattern["params"],
                    }
                )

        return sorted(suggestions, key=lambda x: x["confidence"], reverse=True)[:5]
