from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
from backend.proactive.pattern_engine import PatternEngine, Pattern


@dataclass
class Prediction:
    action_type: str
    suggested_params: dict
    confidence: float
    reasoning: str
    trigger_conditions: dict


class BehaviorPredictor:
    def __init__(self, pattern_engine: PatternEngine):
        self._engine = pattern_engine
        self._prediction_threshold = 0.5
        self._time_window_hours = 24

    async def predict_next_action(self, context: dict = None) -> Optional[Prediction]:
        patterns = await self._engine.detect_patterns()
        if not patterns:
            return None

        scored_patterns = []
        for pattern in patterns:
            score = await self._score_pattern(pattern, context)
            if score >= self._prediction_threshold:
                scored_patterns.append((pattern, score))

        if not scored_patterns:
            return None

        scored_patterns.sort(key=lambda x: x[1], reverse=True)
        best_pattern, confidence = scored_patterns[0]

        return Prediction(
            action_type=best_pattern.action_type,
            suggested_params=best_pattern.typical_params,
            confidence=confidence,
            reasoning=f"Based on {best_pattern.frequency} past occurrences",
            trigger_conditions=self._infer_trigger_conditions(best_pattern),
        )

    async def _score_pattern(self, pattern: Pattern, context: dict) -> float:
        score = pattern.confidence

        recency_bonus = self._compute_recency_bonus(pattern)
        score += recency_bonus * 0.2

        if context:
            context_match = self._compute_context_match(pattern, context)
            score += context_match * 0.3

        return min(1.0, score)

    def _compute_recency_bonus(self, pattern: Pattern) -> float:
        if not pattern.time_patterns:
            return 0.0

        last_occurrence = pattern.last_occurrence
        hours_ago = (datetime.now() - last_occurrence).total_seconds() / 3600

        if hours_ago < 1:
            return 1.0
        elif hours_ago < 6:
            return 0.8
        elif hours_ago < 24:
            return 0.5
        elif hours_ago < 72:
            return 0.3
        else:
            return 0.1

    def _compute_context_match(self, pattern: Pattern, context: dict) -> float:
        if not pattern.typical_params or not context:
            return 0.0

        matches = 0
        total = len(pattern.typical_params)

        for key, value in pattern.typical_params.items():
            if key in context and context[key] == value:
                matches += 1

        return matches / total if total > 0 else 0.0

    def _infer_trigger_conditions(self, pattern: Pattern) -> dict:
        conditions = {}

        times = pattern.time_patterns
        if len(times) >= 3:
            hours = [t.hour for t in times]
            from collections import Counter

            hour_counter = Counter(hours)
            most_common_hour, count = hour_counter.most_common(1)[0]
            if count >= len(times) * 0.5:
                conditions["preferred_hour"] = most_common_hour

        return conditions

    async def get_predictions_for_context(
        self, context: dict, limit: int = 3
    ) -> list[Prediction]:
        patterns = await self._engine.detect_patterns()
        if not patterns:
            return []

        predictions = []
        for pattern in patterns:
            score = await self._score_pattern(pattern, context)
            if score >= self._prediction_threshold:
                predictions.append(
                    Prediction(
                        action_type=pattern.action_type,
                        suggested_params=pattern.typical_params,
                        confidence=score,
                        reasoning=f"Based on {pattern.frequency} past occurrences",
                        trigger_conditions=self._infer_trigger_conditions(pattern),
                    )
                )

        predictions.sort(key=lambda p: p.confidence, reverse=True)
        return predictions[:limit]

    async def should_proactively_act(
        self, prediction: Prediction, context: dict
    ) -> bool:
        if prediction.confidence < self._prediction_threshold:
            return False

        if prediction.trigger_conditions.get("preferred_hour"):
            current_hour = datetime.now().hour
            preferred = prediction.trigger_conditions["preferred_hour"]
            if abs(current_hour - preferred) > 2:
                return False

        return True
