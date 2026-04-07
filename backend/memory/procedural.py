import json
import aiosqlite
from datetime import datetime, timezone
from typing import Dict, List, Optional
from backend.memory.store import PersistentStore


class ProceduralMemory:
    """Learn and recall user patterns/habits."""

    def __init__(self, store: PersistentStore = None):
        self.store = store
        self.patterns: Dict[str, dict] = {}

    def _get_pattern(self, action: str) -> dict:
        """Get or create pattern for an action."""
        if action not in self.patterns:
            self.patterns[action] = {
                "frequency": 0,
                "params": {},
                "timestamps": [],
            }
        return self.patterns[action]

    async def record_action(
        self, action: str, params: dict, timestamp: datetime = None
    ):
        """Record a user action pattern."""
        timestamp = timestamp or datetime.now(timezone.utc)

        pattern = self._get_pattern(action)
        pattern["frequency"] += 1
        pattern["timestamps"].append(timestamp.isoformat())

        if len(pattern["timestamps"]) > 100:
            pattern["timestamps"] = pattern["timestamps"][-100:]

        param_key = json.dumps(params, sort_keys=True)
        if "param_counts" not in pattern:
            pattern["param_counts"] = {}
        pattern["param_counts"][param_key] = (
            pattern["param_counts"].get(param_key, 0) + 1
        )

        max_count = max(pattern["param_counts"].values())
        for pk, count in pattern["param_counts"].items():
            if count == max_count:
                pattern["params"] = json.loads(pk)
                break

        if self.store:
            await self.store.log_task(action, json.dumps(params), "procedural_memory")

    async def load(self):
        """Load patterns from persistent store."""
        if not self.store:
            return

        async with aiosqlite.connect(self.store._db_path) as db:
            async with db.execute(
                "SELECT task, result, created_at FROM task_history WHERE tool='procedural_memory' ORDER BY created_at"
            ) as cur:
                rows = await cur.fetchall()

        for task, result, created_at in rows:
            params = json.loads(result) if result else {}
            pattern = self._get_pattern(task)
            pattern["frequency"] += 1
            pattern["timestamps"].append(created_at)

            param_key = json.dumps(params, sort_keys=True)
            if "param_counts" not in pattern:
                pattern["param_counts"] = {}
            pattern["param_counts"][param_key] = (
                pattern["param_counts"].get(param_key, 0) + 1
            )

            max_count = max(pattern["param_counts"].values())
            for pk, count in pattern["param_counts"].items():
                if count == max_count:
                    pattern["params"] = json.loads(pk)
                    break

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
        """Suggest actions based on patterns. Context reserved for future time-based patterns."""
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
