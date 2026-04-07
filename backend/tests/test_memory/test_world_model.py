import pytest
from unittest.mock import AsyncMock, MagicMock
import tempfile
import os

from backend.memory.world_model import WorldModel
from backend.memory.store import PersistentStore


@pytest.fixture
def mock_store():
    """Create a mock PersistentStore."""
    store = AsyncMock(spec=PersistentStore)
    store.get_preference = AsyncMock(return_value=None)
    store.set_preference = AsyncMock()
    store.get_all_preferences = AsyncMock(return_value={})
    return store


@pytest.fixture
def world_model(mock_store):
    """Create a WorldModel instance with a mock store."""
    return WorldModel(store=mock_store)


def test_world_model_initialization(mock_store):
    """Test WorldModel initializes correctly with store."""
    model = WorldModel(store=mock_store)
    assert model.store == mock_store


def test_world_model_requires_store():
    """Test that WorldModel requires a store parameter."""
    with pytest.raises(TypeError):
        WorldModel()


@pytest.mark.asyncio
async def test_get_preference_delegates_to_store(world_model, mock_store):
    """Test that get_preference calls store.get_preference."""
    mock_store.get_preference.return_value = "New York"

    result = await world_model.get_preference("location")

    mock_store.get_preference.assert_called_once_with("location")
    assert result == "New York"


@pytest.mark.asyncio
async def test_get_preference_returns_none_when_not_set(world_model, mock_store):
    """Test that get_preference returns None when preference not set."""
    mock_store.get_preference.return_value = None

    result = await world_model.get_preference("nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_set_preference_delegates_to_store(world_model, mock_store):
    """Test that set_preference calls store.set_preference."""
    await world_model.set_preference("location", "Paris")

    mock_store.set_preference.assert_called_once_with("location", "Paris")


@pytest.mark.asyncio
async def test_get_user_context_returns_empty_when_no_preferences(
    world_model, mock_store
):
    """Test get_user_context returns empty context when no preferences."""
    mock_store.get_all_preferences.return_value = {}

    context = await world_model.get_user_context()

    assert context["preferences"] == {}
    assert context["context_text"] == ""


@pytest.mark.asyncio
async def test_get_user_context_includes_location(world_model, mock_store):
    """Test get_user_context includes location when set."""
    mock_store.get_all_preferences.return_value = {"location": "New York"}

    context = await world_model.get_user_context()

    assert "User location: New York" in context["context_text"]


@pytest.mark.asyncio
async def test_get_user_context_includes_timezone(world_model, mock_store):
    """Test get_user_context includes timezone when set."""
    mock_store.get_all_preferences.return_value = {"timezone": "America/New_York"}

    context = await world_model.get_user_context()

    assert "User timezone: America/New_York" in context["context_text"]


@pytest.mark.asyncio
async def test_get_user_context_includes_name(world_model, mock_store):
    """Test get_user_context includes name when set."""
    mock_store.get_all_preferences.return_value = {"name": "Alice"}

    context = await world_model.get_user_context()

    assert "User name: Alice" in context["context_text"]


@pytest.mark.asyncio
async def test_get_user_context_includes_multiple_preferences(world_model, mock_store):
    """Test get_user_context includes all known preferences."""
    mock_store.get_all_preferences.return_value = {
        "location": "New York",
        "timezone": "America/New_York",
        "name": "Alice",
        "other_pref": "ignored",
    }

    context = await world_model.get_user_context()

    assert "User location: New York" in context["context_text"]
    assert "User timezone: America/New_York" in context["context_text"]
    assert "User name: Alice" in context["context_text"]
    assert "other_pref" not in context["context_text"]


@pytest.mark.asyncio
async def test_get_user_context_returns_full_preferences(world_model, mock_store):
    """Test get_user_context returns all preferences in dict."""
    mock_store.get_all_preferences.return_value = {
        "location": "New York",
        "other_pref": "value",
    }

    context = await world_model.get_user_context()

    assert context["preferences"]["location"] == "New York"
    assert context["preferences"]["other_pref"] == "value"


@pytest.mark.asyncio
async def test_infer_preference_from_weather_action(world_model, mock_store):
    """Test that infer_preference stores location from check_weather action."""
    mock_store.get_preference.return_value = None

    await world_model.infer_preference("check_weather", {"location": "Seattle"})

    mock_store.set_preference.assert_called_once_with("location", "Seattle")


@pytest.mark.asyncio
async def test_infer_preference_does_not_override_existing(world_model, mock_store):
    """Test that infer_preference does not override existing preference."""
    mock_store.get_preference.return_value = "Existing City"

    await world_model.infer_preference("check_weather", {"location": "Seattle"})

    mock_store.set_preference.assert_not_called()


@pytest.mark.asyncio
async def test_infer_preference_ignores_action_without_location(
    world_model, mock_store
):
    """Test that infer_preference ignores actions without location param."""
    await world_model.infer_preference("check_weather", {"unit": "celsius"})

    mock_store.set_preference.assert_not_called()


@pytest.mark.asyncio
async def test_infer_preference_ignores_other_actions(world_model, mock_store):
    """Test that infer_preference ignores non-weather actions."""
    await world_model.infer_preference("play_music", {"location": "Seattle"})

    mock_store.set_preference.assert_not_called()


@pytest.mark.asyncio
async def test_world_model_with_real_store():
    """Test WorldModel with actual PersistentStore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")

        store = PersistentStore()
        store._db_path = db_path
        await store.init()

        model = WorldModel(store=store)

        await model.set_preference("location", "Tokyo")
        result = await model.get_preference("location")
        assert result == "Tokyo"

        context = await model.get_user_context()
        assert "User location: Tokyo" in context["context_text"]


@pytest.mark.asyncio
async def test_infer_preference_with_real_store():
    """Test infer_preference with actual PersistentStore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")

        store = PersistentStore()
        store._db_path = db_path
        await store.init()

        model = WorldModel(store=store)

        await model.infer_preference("check_weather", {"location": "Berlin"})

        result = await model.get_preference("location")
        assert result == "Berlin"
