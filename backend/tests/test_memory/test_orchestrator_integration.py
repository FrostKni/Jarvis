import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from backend.brain.orchestrator import JarvisOrchestrator
from backend.brain.llm import LLMClient
from backend.brain.router import IntentRouter
from backend.memory.assembler import MemoryAssembler
from backend.memory.session import SessionCache
from backend.memory.vector import VectorMemory
from backend.memory.procedural import ProceduralMemory
from backend.memory.world_model import WorldModel
from backend.tools.registry import ToolExecutor
from backend.memory.store import PersistentStore


@pytest.fixture
def mock_llm():
    llm = AsyncMock(spec=LLMClient)
    return llm


@pytest.fixture
def mock_router():
    router = AsyncMock(spec=IntentRouter)
    router.route = AsyncMock(return_value={"needs_tools": False, "complexity": "fast"})
    return router


@pytest.fixture
def mock_assembler():
    assembler = AsyncMock(spec=MemoryAssembler)
    assembler.build_context = AsyncMock(return_value="Test context")
    return assembler


@pytest.fixture
def mock_session():
    session = AsyncMock(spec=SessionCache)
    session.get_turns = AsyncMock(return_value=[])
    session.add_turn = AsyncMock()
    return session


@pytest.fixture
def mock_vector():
    vector = MagicMock(spec=VectorMemory)
    vector.store = MagicMock()
    return vector


@pytest.fixture
def mock_executor():
    executor = AsyncMock(spec=ToolExecutor)
    executor.execute = AsyncMock(return_value="tool result")
    return executor


@pytest.fixture
def procedural_memory():
    return ProceduralMemory()


@pytest.fixture
def world_model():
    store = AsyncMock(spec=PersistentStore)
    store.get_preference = AsyncMock(return_value=None)
    store.set_preference = AsyncMock()
    return WorldModel(store=store)


def test_orchestrator_initialization_with_procedural_and_world_model(
    mock_llm,
    mock_router,
    mock_assembler,
    mock_session,
    mock_vector,
    mock_executor,
    procedural_memory,
    world_model,
):
    orchestrator = JarvisOrchestrator(
        llm=mock_llm,
        router=mock_router,
        assembler=mock_assembler,
        session=mock_session,
        vector=mock_vector,
        executor=mock_executor,
        procedural=procedural_memory,
        world_model=world_model,
    )

    assert orchestrator.procedural == procedural_memory
    assert orchestrator.world_model == world_model


def test_orchestrator_initialization_without_procedural_and_world_model(
    mock_llm, mock_router, mock_assembler, mock_session, mock_vector, mock_executor
):
    orchestrator = JarvisOrchestrator(
        llm=mock_llm,
        router=mock_router,
        assembler=mock_assembler,
        session=mock_session,
        vector=mock_vector,
        executor=mock_executor,
    )

    assert orchestrator.procedural is None
    assert orchestrator.world_model is None


@pytest.mark.asyncio
async def test_record_tool_usage_calls_both(
    mock_llm,
    mock_router,
    mock_assembler,
    mock_session,
    mock_vector,
    mock_executor,
    procedural_memory,
    world_model,
):
    orchestrator = JarvisOrchestrator(
        llm=mock_llm,
        router=mock_router,
        assembler=mock_assembler,
        session=mock_session,
        vector=mock_vector,
        executor=mock_executor,
        procedural=procedural_memory,
        world_model=world_model,
    )

    await orchestrator._record_tool_usage("check_weather", {"location": "Seattle"})

    assert "check_weather" in procedural_memory.patterns
    assert procedural_memory.patterns["check_weather"]["frequency"] == 1
    world_model.store.set_preference.assert_called_once_with("location", "Seattle")


@pytest.mark.asyncio
async def test_record_tool_usage_only_procedural(
    mock_llm,
    mock_router,
    mock_assembler,
    mock_session,
    mock_vector,
    mock_executor,
    procedural_memory,
):
    orchestrator = JarvisOrchestrator(
        llm=mock_llm,
        router=mock_router,
        assembler=mock_assembler,
        session=mock_session,
        vector=mock_vector,
        executor=mock_executor,
        procedural=procedural_memory,
        world_model=None,
    )

    await orchestrator._record_tool_usage("play_music", {"genre": "rock"})

    assert "play_music" in procedural_memory.patterns


@pytest.mark.asyncio
async def test_record_tool_usage_only_world_model(
    mock_llm,
    mock_router,
    mock_assembler,
    mock_session,
    mock_vector,
    mock_executor,
    world_model,
):
    orchestrator = JarvisOrchestrator(
        llm=mock_llm,
        router=mock_router,
        assembler=mock_assembler,
        session=mock_session,
        vector=mock_vector,
        executor=mock_executor,
        procedural=None,
        world_model=world_model,
    )

    await orchestrator._record_tool_usage("check_weather", {"location": "Tokyo"})

    world_model.store.set_preference.assert_called_once_with("location", "Tokyo")


@pytest.mark.asyncio
async def test_record_tool_usage_skipped_when_none(
    mock_llm, mock_router, mock_assembler, mock_session, mock_vector, mock_executor
):
    orchestrator = JarvisOrchestrator(
        llm=mock_llm,
        router=mock_router,
        assembler=mock_assembler,
        session=mock_session,
        vector=mock_vector,
        executor=mock_executor,
        procedural=None,
        world_model=None,
    )

    await orchestrator._record_tool_usage("some_tool", {"param": "value"})


@pytest.mark.asyncio
async def test_agentic_loop_records_tool_usage(
    mock_llm,
    mock_router,
    mock_assembler,
    mock_session,
    mock_vector,
    mock_executor,
    procedural_memory,
    world_model,
):
    mock_response = MagicMock()
    mock_response.stop_reason = "tool_use"
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "check_weather"
    mock_block.input = {"location": "Paris"}
    mock_block.id = "tool_123"
    mock_response.content = [mock_block]

    mock_end_response = MagicMock()
    mock_end_response.stop_reason = "end_turn"
    mock_end_response.content = [MagicMock(text="Done!")]

    mock_llm.complete_with_tools = AsyncMock(
        side_effect=[mock_response, mock_end_response]
    )

    orchestrator = JarvisOrchestrator(
        llm=mock_llm,
        router=mock_router,
        assembler=mock_assembler,
        session=mock_session,
        vector=mock_vector,
        executor=mock_executor,
        procedural=procedural_memory,
        world_model=world_model,
    )

    result = await orchestrator._agentic_loop([], "system")

    assert result == "Done!"
    assert "check_weather" in procedural_memory.patterns
    world_model.store.set_preference.assert_called_once_with("location", "Paris")


@pytest.mark.asyncio
async def test_agentic_loop_records_multiple_tools(
    mock_llm,
    mock_router,
    mock_assembler,
    mock_session,
    mock_vector,
    mock_executor,
    procedural_memory,
):
    def make_tool_response(tool_name, tool_input):
        mock_response = MagicMock()
        mock_response.stop_reason = "tool_use"
        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.name = tool_name
        mock_block.input = tool_input
        mock_block.id = f"tool_{tool_name}"
        mock_response.content = [mock_block]
        return mock_response

    mock_end_response = MagicMock()
    mock_end_response.stop_reason = "end_turn"
    mock_end_response.content = [MagicMock(text="All done!")]

    mock_llm.complete_with_tools = AsyncMock(
        side_effect=[
            make_tool_response("check_weather", {"location": "NYC"}),
            make_tool_response("play_music", {"genre": "jazz"}),
            mock_end_response,
        ]
    )

    orchestrator = JarvisOrchestrator(
        llm=mock_llm,
        router=mock_router,
        assembler=mock_assembler,
        session=mock_session,
        vector=mock_vector,
        executor=mock_executor,
        procedural=procedural_memory,
        world_model=None,
    )

    result = await orchestrator._agentic_loop([], "system")

    assert result == "All done!"
    assert "check_weather" in procedural_memory.patterns
    assert "play_music" in procedural_memory.patterns
    assert procedural_memory.patterns["check_weather"]["frequency"] == 1
    assert procedural_memory.patterns["play_music"]["frequency"] == 1
