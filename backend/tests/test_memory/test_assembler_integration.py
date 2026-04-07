import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import os

from backend.memory.assembler import MemoryAssembler
from backend.memory.vector import VectorMemory
from backend.memory.graph import GraphMemory
from backend.memory.store import PersistentStore
from backend.memory.procedural import ProceduralMemory
from backend.memory.world_model import WorldModel


@pytest.fixture
def mock_vector():
    vector = MagicMock(spec=VectorMemory)
    vector.search = MagicMock(return_value=["memory 1", "memory 2"])
    return vector


@pytest.fixture
def mock_graph():
    graph = AsyncMock(spec=GraphMemory)
    graph.get_context_for = AsyncMock(return_value="Alice is a friend")
    graph.close = AsyncMock()
    return graph


@pytest.fixture
def mock_store():
    store = AsyncMock(spec=PersistentStore)
    store.get_all_preferences = AsyncMock(return_value={"location": "New York"})
    return store


@pytest.fixture
def procedural_with_patterns():
    memory = ProceduralMemory()
    memory.patterns = {
        "play_music": {
            "frequency": 5,
            "params": {"genre": "rock"},
            "timestamps": ["2026-01-01"],
        },
        "check_weather": {
            "frequency": 3,
            "params": {"location": "NYC"},
            "timestamps": ["2026-01-02"],
        },
    }
    return memory


@pytest.fixture
def world_model_with_prefs(mock_store):
    return WorldModel(store=mock_store)


def test_assembler_initialization_with_all_components(
    mock_vector, mock_graph, mock_store
):
    procedural = ProceduralMemory()
    world_model = WorldModel(store=mock_store)

    assembler = MemoryAssembler(
        vector=mock_vector,
        graph=mock_graph,
        store=mock_store,
        procedural=procedural,
        world_model=world_model,
    )

    assert assembler.vector == mock_vector
    assert assembler.graph == mock_graph
    assert assembler.store == mock_store
    assert assembler.procedural == procedural
    assert assembler.world_model == world_model


def test_assembler_initialization_without_procedural_world_model(
    mock_vector, mock_graph, mock_store
):
    assembler = MemoryAssembler(
        vector=mock_vector,
        graph=mock_graph,
        store=mock_store,
    )

    assert assembler.procedural is None
    assert assembler.world_model is None


@pytest.mark.asyncio
async def test_build_context_with_world_model(mock_vector, mock_graph, mock_store):
    world_model = WorldModel(store=mock_store)
    assembler = MemoryAssembler(
        vector=mock_vector,
        graph=mock_graph,
        store=mock_store,
        world_model=world_model,
    )

    context = await assembler.build_context("What's the weather for Alice?")

    assert "User preferences:" in context
    assert "location: New York" in context
    assert "Relevant memories:" in context
    assert "Known relationships:" in context


@pytest.mark.asyncio
async def test_build_context_without_world_model_uses_fallback(
    mock_vector, mock_graph, mock_store
):
    assembler = MemoryAssembler(
        vector=mock_vector,
        graph=mock_graph,
        store=mock_store,
    )

    context = await assembler.build_context("Hello")

    assert "User preferences:" in context
    assert "location: New York" in context


@pytest.mark.asyncio
async def test_build_context_includes_procedural_suggestions(
    mock_vector, mock_graph, mock_store, procedural_with_patterns
):
    world_model = WorldModel(store=mock_store)
    assembler = MemoryAssembler(
        vector=mock_vector,
        graph=mock_graph,
        store=mock_store,
        procedural=procedural_with_patterns,
        world_model=world_model,
    )

    context = await assembler.build_context("Hello")

    assert "Common actions:" in context
    assert "play_music" in context
    assert "check_weather" in context


@pytest.mark.asyncio
async def test_build_context_without_procedural_no_suggestions(
    mock_vector, mock_graph, mock_store
):
    world_model = WorldModel(store=mock_store)
    assembler = MemoryAssembler(
        vector=mock_vector,
        graph=mock_graph,
        store=mock_store,
        world_model=world_model,
    )

    context = await assembler.build_context("Hello")

    assert "Common actions:" not in context


@pytest.mark.asyncio
async def test_build_context_all_parts_combined(
    mock_vector, mock_graph, mock_store, procedural_with_patterns
):
    mock_store.get_all_preferences.return_value = {
        "location": "Boston",
        "timezone": "America/New_York",
        "name": "Alice",
    }
    world_model = WorldModel(store=mock_store)
    assembler = MemoryAssembler(
        vector=mock_vector,
        graph=mock_graph,
        store=mock_store,
        procedural=procedural_with_patterns,
        world_model=world_model,
    )

    context = await assembler.build_context("What's up with Alice?")

    assert "User preferences:" in context
    assert "location: Boston" in context
    assert "Relevant memories:" in context
    assert "Known relationships:" in context
    assert "Common actions:" in context


@pytest.mark.asyncio
async def test_fallback_user_context(mock_store):
    assembler = MemoryAssembler(
        vector=MagicMock(),
        graph=AsyncMock(),
        store=mock_store,
    )

    result = await assembler._fallback_user_context()

    assert result["preferences"] == {"location": "New York"}
    assert result["context_text"] == ""


@pytest.mark.asyncio
async def test_integration_with_real_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")

        store = PersistentStore()
        store._db_path = db_path
        await store.init()

        await store.set_preference("location", "Seattle")
        await store.set_preference("name", "Bob")

        procedural = ProceduralMemory(store=store)
        await procedural.record_action("play_music", {"genre": "jazz"})
        await procedural.record_action("play_music", {"genre": "jazz"})
        await procedural.record_action("play_music", {"genre": "jazz"})

        world_model = WorldModel(store=store)

        vector = MagicMock()
        vector.search = MagicMock(return_value=["past conversation"])

        graph = AsyncMock()
        graph.get_context_for = AsyncMock(return_value=None)

        assembler = MemoryAssembler(vector, graph, store, procedural, world_model)

        context = await assembler.build_context("Play some music")

        assert "User preferences:" in context
        assert "location: Seattle" in context
        assert "name: Bob" in context
        assert "past conversation" in context
        assert "Common actions:" in context
        assert "play_music" in context
