import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class UserAction:
    action_type: str
    parameters: dict
    timestamp: datetime
    context: dict = field(default_factory=dict)


@dataclass
class Pattern:
    action_type: str
    frequency: int
    last_occurrence: datetime
    typical_params: dict
    time_patterns: list[datetime]
    confidence: float


class PatternEngine:
    def __init__(self, max_history: int = 1000):
        self._action_history: list[UserAction] = []
        self._patterns: dict[str, Pattern] = {}
        self._max_history = max_history
        self._action_counts: dict[str, int] = defaultdict(int)
        self._param_history: dict[str, list[dict]] = defaultdict(list)
        self._time_history: dict[str, list[datetime]] = defaultdict(list)

    async def record_action(
        self, action_type: str, parameters: dict, context: dict = None
    ) -> None:
        action = UserAction(
            action_type=action_type,
            parameters=parameters,
            timestamp=datetime.now(),
            context=context or {},
        )
        self._action_history.append(action)
        if len(self._action_history) > self._max_history:
            removed = self._action_history.pop(0)
            self._action_counts[removed.action_type] = max(
                0, self._action_counts[removed.action_type] - 1
            )

        self._action_counts[action_type] += 1
        self._param_history[action_type].append(parameters)
        if len(self._param_history[action_type]) > 100:
            self._param_history[action_type].pop(0)
        self._time_history[action_type].append(action.timestamp)
        if len(self._time_history[action_type]) > 100:
            self._time_history[action_type].pop(0)

        await self._update_patterns(action_type)

    async def _update_patterns(self, action_type: str) -> None:
        count = self._action_counts[action_type]
        if count < 3:
            return

        params_list = self._param_history[action_type]
        typical_params = self._compute_typical_params(params_list)

        times = self._time_history[action_type]
        confidence = min(1.0, count / 10.0)

        self._patterns[action_type] = Pattern(
            action_type=action_type,
            frequency=count,
            last_occurrence=times[-1] if times else datetime.now(),
            typical_params=typical_params,
            time_patterns=times,
            confidence=confidence,
        )

    def _compute_typical_params(self, params_list: list[dict]) -> dict:
        if not params_list:
            return {}

        typical = {}
        all_keys = set()
        for p in params_list:
            all_keys.update(p.keys())

        for key in all_keys:
            values = [p.get(key) for p in params_list if key in p]
            if not values:
                continue

            if isinstance(values[0], str):
                from collections import Counter

                counter = Counter(values)
                typical[key] = counter.most_common(1)[0][0]
            elif isinstance(values[0], (int, float)):
                typical[key] = sum(values) / len(values)
            else:
                typical[key] = values[-1]

        return typical

    async def detect_patterns(self) -> list[Pattern]:
        return list(self._patterns.values())

    async def get_pattern(self, action_type: str) -> Optional[Pattern]:
        return self._patterns.get(action_type)

    async def get_frequent_actions(self, min_frequency: int = 3) -> list[str]:
        return [
            action
            for action, count in self._action_counts.items()
            if count >= min_frequency
        ]

    async def clear_history(self) -> None:
        self._action_history.clear()
        self._patterns.clear()
        self._action_counts.clear()
        self._param_history.clear()
        self._time_history.clear()
