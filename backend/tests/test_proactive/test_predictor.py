import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from backend.proactive.predictor import BehaviorPredictor, Prediction
from backend.proactive.pattern_engine import PatternEngine, Pattern


@pytest.fixture
def pattern_engine():
    return PatternEngine(max_history=100)


@pytest.fixture
def predictor(pattern_engine):
    return BehaviorPredictor(pattern_engine)


@pytest.mark.asyncio
async def test_predict_no_patterns(predictor):
    prediction = await predictor.predict_next_action()
    assert prediction is None


@pytest.mark.asyncio
async def test_predict_with_patterns(predictor, pattern_engine):
    for i in range(5):
        await pattern_engine.record_action(
            action_type="web_search",
            parameters={"query": "weather"},
        )

    prediction = await predictor.predict_next_action()
    assert prediction is not None
    assert prediction.action_type == "web_search"
    assert prediction.confidence > 0


@pytest.mark.asyncio
async def test_prediction_scoring(predictor, pattern_engine):
    for i in range(10):
        await pattern_engine.record_action(
            action_type="high_frequency",
            parameters={"param": "value"},
        )

    for i in range(3):
        await pattern_engine.record_action(
            action_type="low_frequency",
            parameters={"param": "value"},
        )

    prediction = await predictor.predict_next_action()
    assert prediction is not None
    assert prediction.action_type == "high_frequency"


@pytest.mark.asyncio
async def test_get_predictions_for_context(predictor, pattern_engine):
    for i in range(5):
        await pattern_engine.record_action(
            action_type="send_email",
            parameters={"to": "user@example.com", "subject": "Test"},
        )

    for i in range(5):
        await pattern_engine.record_action(
            action_type="web_search",
            parameters={"query": "news"},
        )

    predictions = await predictor.get_predictions_for_context({}, limit=3)
    assert len(predictions) <= 3
    assert all(isinstance(p, Prediction) for p in predictions)


@pytest.mark.asyncio
async def test_should_proactively_act(predictor, pattern_engine):
    for i in range(10):
        await pattern_engine.record_action(
            action_type="routine_task",
            parameters={"param": "value"},
        )

    prediction = await predictor.predict_next_action()
    assert prediction is not None

    should_act = await predictor.should_proactively_act(prediction, {})
    assert isinstance(should_act, bool)


@pytest.mark.asyncio
async def test_trigger_conditions_inferred(predictor, pattern_engine):
    base_time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    for i in range(5):
        pattern_engine._time_history["morning_task"].append(base_time)
        pattern_engine._action_counts["morning_task"] += 1
        pattern_engine._param_history["morning_task"].append({"param": "value"})

    await pattern_engine._update_patterns("morning_task")

    prediction = await predictor.predict_next_action()
    if prediction:
        assert isinstance(prediction.trigger_conditions, dict)
