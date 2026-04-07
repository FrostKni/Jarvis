import pytest
from datetime import datetime, timedelta
from backend.proactive.pattern_engine import PatternEngine, Pattern


@pytest.fixture
def pattern_engine():
    return PatternEngine(max_history=100)


@pytest.mark.asyncio
async def test_record_action(pattern_engine):
    await pattern_engine.record_action(
        action_type="web_search", parameters={"query": "test"}
    )

    frequent = await pattern_engine.get_frequent_actions(min_frequency=1)
    assert "web_search" in frequent


@pytest.mark.asyncio
async def test_pattern_detection(pattern_engine):
    for i in range(5):
        await pattern_engine.record_action(
            action_type="send_email",
            parameters={"to": "user@example.com", "subject": f"Test {i}"},
        )

    patterns = await pattern_engine.detect_patterns()
    assert len(patterns) > 0

    email_pattern = next((p for p in patterns if p.action_type == "send_email"), None)
    assert email_pattern is not None
    assert email_pattern.frequency == 5
    assert email_pattern.confidence > 0


@pytest.mark.asyncio
async def test_typical_params_computation(pattern_engine):
    for i in range(5):
        await pattern_engine.record_action(
            action_type="navigate_url",
            parameters={"url": "https://example.com", "wait_for": ".content"},
        )

    pattern = await pattern_engine.get_pattern("navigate_url")
    assert pattern is not None
    assert pattern.typical_params.get("url") == "https://example.com"


@pytest.mark.asyncio
async def test_get_pattern_not_found(pattern_engine):
    pattern = await pattern_engine.get_pattern("nonexistent_action")
    assert pattern is None


@pytest.mark.asyncio
async def test_clear_history(pattern_engine):
    await pattern_engine.record_action("test_action", {"param": "value"})
    await pattern_engine.clear_history()

    frequent = await pattern_engine.get_frequent_actions()
    assert len(frequent) == 0


@pytest.mark.asyncio
async def test_max_history_limit():
    engine = PatternEngine(max_history=10)

    for i in range(20):
        await engine.record_action(f"action_{i}", {})

    frequent = await engine.get_frequent_actions(min_frequency=1)
    assert len(frequent) <= 10


@pytest.mark.asyncio
async def test_pattern_confidence_increases(pattern_engine):
    for i in range(10):
        await pattern_engine.record_action("repeated_action", {"param": "value"})

    pattern = await pattern_engine.get_pattern("repeated_action")
    assert pattern.confidence == 1.0
