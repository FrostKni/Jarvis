import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import os
import aiosqlite

from backend.memory.procedural import ProceduralMemory
from backend.memory.store import PersistentStore


@pytest.fixture
def procedural_memory():
    """Create a ProceduralMemory instance without a store."""
    return ProceduralMemory()


@pytest.fixture
def procedural_memory_with_store():
    """Create a ProceduralMemory instance with a mock store."""
    mock_store = AsyncMock()
    mock_store.log_task = AsyncMock()
    return ProceduralMemory(store=mock_store), mock_store


def test_procedural_memory_initialization(procedural_memory):
    """Test ProceduralMemory initializes correctly."""
    assert procedural_memory.store is None
    assert isinstance(procedural_memory.patterns, dict)


def test_procedural_memory_with_store():
    """Test ProceduralMemory initializes with a store."""
    mock_store = MagicMock()
    memory = ProceduralMemory(store=mock_store)
    assert memory.store == mock_store


@pytest.mark.asyncio
async def test_record_action_increases_frequency(procedural_memory):
    """Test that recording an action increases its frequency."""
    await procedural_memory.record_action("play_music", {"genre": "rock"})

    assert procedural_memory.patterns["play_music"]["frequency"] == 1


@pytest.mark.asyncio
async def test_record_action_stores_timestamp(procedural_memory):
    """Test that recording an action stores timestamp."""
    timestamp = datetime(2026, 4, 7, 12, 0, 0)
    await procedural_memory.record_action(
        "play_music", {"genre": "rock"}, timestamp=timestamp
    )

    assert (
        "2026-04-07T12:00:00"
        in procedural_memory.patterns["play_music"]["timestamps"][0]
    )


@pytest.mark.asyncio
async def test_record_action_uses_current_time_if_no_timestamp(procedural_memory):
    """Test that record_action uses current time if no timestamp provided."""
    before = datetime.now(timezone.utc)
    await procedural_memory.record_action("play_music", {"genre": "rock"})
    after = datetime.now(timezone.utc)

    stored_time = datetime.fromisoformat(
        procedural_memory.patterns["play_music"]["timestamps"][0]
    )
    assert before <= stored_time <= after


@pytest.mark.asyncio
async def test_record_action_tracks_params(procedural_memory):
    """Test that recording an action tracks parameters."""
    await procedural_memory.record_action("play_music", {"genre": "rock"})

    assert procedural_memory.patterns["play_music"]["params"] == {"genre": "rock"}


@pytest.mark.asyncio
async def test_record_action_tracks_most_common_params(procedural_memory):
    """Test that the most common params are tracked."""
    await procedural_memory.record_action("play_music", {"genre": "rock"})
    await procedural_memory.record_action("play_music", {"genre": "jazz"})
    await procedural_memory.record_action("play_music", {"genre": "rock"})

    assert procedural_memory.patterns["play_music"]["params"] == {"genre": "rock"}


@pytest.mark.asyncio
async def test_record_action_with_store_persists(procedural_memory_with_store):
    """Test that recording an action with store persists to store."""
    memory, mock_store = procedural_memory_with_store
    await memory.record_action("play_music", {"genre": "rock"})

    mock_store.log_task.assert_called_once_with(
        "play_music", '{"genre": "rock"}', "procedural_memory"
    )


@pytest.mark.asyncio
async def test_get_pattern_returns_none_if_frequency_less_than_3(procedural_memory):
    """Test that get_pattern returns None if frequency < 3."""
    await procedural_memory.record_action("play_music", {"genre": "rock"})
    await procedural_memory.record_action("play_music", {"genre": "rock"})

    result = await procedural_memory.get_pattern("play_music")

    assert result is None


@pytest.mark.asyncio
async def test_get_pattern_returns_pattern_if_frequency_3_or_more(procedural_memory):
    """Test that get_pattern returns pattern if frequency >= 3."""
    for _ in range(3):
        await procedural_memory.record_action("play_music", {"genre": "rock"})

    result = await procedural_memory.get_pattern("play_music")

    assert result is not None
    assert result["action"] == "play_music"
    assert result["frequency"] == 3
    assert result["params"] == {"genre": "rock"}
    assert result["last_occurred"] is not None


@pytest.mark.asyncio
async def test_get_pattern_returns_none_for_nonexistent_action(procedural_memory):
    """Test that get_pattern returns None for nonexistent action."""
    result = await procedural_memory.get_pattern("nonexistent_action")

    assert result is None


@pytest.mark.asyncio
async def test_get_pattern_returns_last_timestamp(procedural_memory):
    """Test that get_pattern returns the last timestamp."""
    ts1 = datetime(2026, 4, 7, 10, 0, 0)
    ts2 = datetime(2026, 4, 7, 11, 0, 0)
    ts3 = datetime(2026, 4, 7, 12, 0, 0)

    await procedural_memory.record_action(
        "play_music", {"genre": "rock"}, timestamp=ts1
    )
    await procedural_memory.record_action(
        "play_music", {"genre": "rock"}, timestamp=ts2
    )
    await procedural_memory.record_action(
        "play_music", {"genre": "rock"}, timestamp=ts3
    )

    result = await procedural_memory.get_pattern("play_music")

    assert result["last_occurred"] == "2026-04-07T12:00:00"


@pytest.mark.asyncio
async def test_suggest_actions_returns_empty_if_no_patterns(procedural_memory):
    """Test that suggest_actions returns empty list if no learned patterns."""
    suggestions = await procedural_memory.suggest_actions()

    assert suggestions == []


@pytest.mark.asyncio
async def test_suggest_actions_excludes_patterns_below_threshold(procedural_memory):
    """Test that suggest_actions excludes patterns with frequency < 3."""
    await procedural_memory.record_action("play_music", {"genre": "rock"})
    await procedural_memory.record_action("play_music", {"genre": "rock"})

    suggestions = await procedural_memory.suggest_actions()

    assert suggestions == []


@pytest.mark.asyncio
async def test_suggest_actions_includes_patterns_above_threshold(procedural_memory):
    """Test that suggest_actions includes patterns with frequency >= 3."""
    for _ in range(3):
        await procedural_memory.record_action("play_music", {"genre": "rock"})

    suggestions = await procedural_memory.suggest_actions()

    assert len(suggestions) == 1
    assert suggestions[0]["action"] == "play_music"
    assert suggestions[0]["params"] == {"genre": "rock"}


@pytest.mark.asyncio
async def test_suggest_actions_calculates_confidence(procedural_memory):
    """Test that suggest_actions calculates confidence correctly."""
    for _ in range(5):
        await procedural_memory.record_action("play_music", {"genre": "rock"})

    suggestions = await procedural_memory.suggest_actions()

    assert suggestions[0]["confidence"] == 0.5


@pytest.mark.asyncio
async def test_suggest_actions_confidence_cap_at_1(procedural_memory):
    """Test that confidence is capped at 1.0."""
    for _ in range(15):
        await procedural_memory.record_action("play_music", {"genre": "rock"})

    suggestions = await procedural_memory.suggest_actions()

    assert suggestions[0]["confidence"] == 1.0


@pytest.mark.asyncio
async def test_suggest_actions_sorted_by_confidence(procedural_memory):
    """Test that suggestions are sorted by confidence (descending)."""
    for _ in range(3):
        await procedural_memory.record_action("action_a", {"param": "a"})
    for _ in range(5):
        await procedural_memory.record_action("action_b", {"param": "b"})
    for _ in range(7):
        await procedural_memory.record_action("action_c", {"param": "c"})

    suggestions = await procedural_memory.suggest_actions()

    assert suggestions[0]["action"] == "action_c"
    assert suggestions[1]["action"] == "action_b"
    assert suggestions[2]["action"] == "action_a"


@pytest.mark.asyncio
async def test_suggest_actions_limits_to_5_results(procedural_memory):
    """Test that suggest_actions limits results to 5."""
    for i in range(6):
        for _ in range(3):
            await procedural_memory.record_action(f"action_{i}", {"param": i})

    suggestions = await procedural_memory.suggest_actions()

    assert len(suggestions) == 5


@pytest.mark.asyncio
async def test_suggest_actions_ignores_context(procedural_memory):
    """Test that suggest_actions works with None context (placeholder)."""
    for _ in range(3):
        await procedural_memory.record_action("play_music", {"genre": "rock"})

    suggestions = await procedural_memory.suggest_actions(context={"time": "morning"})

    assert len(suggestions) == 1


@pytest.mark.asyncio
async def test_multiple_different_actions(procedural_memory):
    """Test tracking multiple different actions."""
    await procedural_memory.record_action("play_music", {"genre": "rock"})
    await procedural_memory.record_action("set_timer", {"minutes": 10})
    await procedural_memory.record_action("play_music", {"genre": "jazz"})

    assert procedural_memory.patterns["play_music"]["frequency"] == 2
    assert procedural_memory.patterns["set_timer"]["frequency"] == 1


@pytest.mark.asyncio
async def test_params_with_different_keys(procedural_memory):
    """Test tracking params with different keys."""
    await procedural_memory.record_action(
        "complex_action", {"key1": "value1", "key2": "value2"}
    )
    await procedural_memory.record_action(
        "complex_action", {"key1": "value1", "key2": "value2"}
    )
    await procedural_memory.record_action(
        "complex_action", {"key1": "value1", "key2": "value2"}
    )

    result = await procedural_memory.get_pattern("complex_action")

    assert result["params"] == {"key1": "value1", "key2": "value2"}


@pytest.mark.asyncio
async def test_empty_params(procedural_memory):
    """Test recording actions with empty params."""
    await procedural_memory.record_action("simple_action", {})
    await procedural_memory.record_action("simple_action", {})
    await procedural_memory.record_action("simple_action", {})

    result = await procedural_memory.get_pattern("simple_action")

    assert result["params"] == {}
    assert result["frequency"] == 3


@pytest.mark.asyncio
async def test_load_patterns_from_store():
    """Test that load() restores patterns from persistent store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")

        store = PersistentStore()
        store._db_path = db_path
        await store.init()

        await store.log_task("play_music", '{"genre": "rock"}', "procedural_memory")
        await store.log_task("play_music", '{"genre": "rock"}', "procedural_memory")
        await store.log_task("play_music", '{"genre": "jazz"}', "procedural_memory")
        await store.log_task("set_timer", '{"minutes": 5}', "procedural_memory")

        memory = ProceduralMemory(store=store)
        await memory.load()

        assert memory.patterns["play_music"]["frequency"] == 3
        assert memory.patterns["set_timer"]["frequency"] == 1
        assert memory.patterns["play_music"]["params"] == {"genre": "rock"}
        assert len(memory.patterns["play_music"]["timestamps"]) == 3


@pytest.mark.asyncio
async def test_load_without_store():
    """Test that load() does nothing when no store is configured."""
    memory = ProceduralMemory()
    await memory.load()

    assert memory.patterns == {}


@pytest.mark.asyncio
async def test_timestamp_bounded_at_100():
    """Test that timestamps are bounded at 100 entries."""
    memory = ProceduralMemory()

    for i in range(150):
        await memory.record_action("frequent_action", {"count": i})

    assert len(memory.patterns["frequent_action"]["timestamps"]) == 100
