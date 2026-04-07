import pytest
from unittest.mock import AsyncMock, MagicMock
import json

from backend.memory.consolidator import MemoryConsolidator


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.complete = AsyncMock()
    return llm


@pytest.fixture
def mock_vector():
    vector = MagicMock()
    vector.store = MagicMock()
    return vector


@pytest.fixture
def mock_world_model():
    model = MagicMock()
    model.set_preference = AsyncMock()
    return model


@pytest.fixture
def mock_graph():
    graph = MagicMock()
    graph.upsert_entity = AsyncMock()
    return graph


@pytest.fixture
def consolidator(mock_llm, mock_vector, mock_world_model, mock_graph):
    return MemoryConsolidator(
        llm=mock_llm,
        vector=mock_vector,
        world_model=mock_world_model,
        graph=mock_graph,
    )


def test_consolidator_initialization(
    consolidator, mock_llm, mock_vector, mock_world_model, mock_graph
):
    assert consolidator.llm == mock_llm
    assert consolidator.vector == mock_vector
    assert consolidator.world_model == mock_world_model
    assert consolidator.graph == mock_graph


def test_consolidator_requires_all_dependencies():
    with pytest.raises(TypeError):
        MemoryConsolidator()


@pytest.mark.asyncio
async def test_consolidate_skips_empty_turns(consolidator):
    result = await consolidator.consolidate("session-123", [])

    assert result["status"] == "skipped"
    assert result["reason"] == "no turns"


@pytest.mark.asyncio
async def test_consolidate_formats_turns_correctly(consolidator):
    turns = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]

    formatted = consolidator._format_turns(turns)

    assert "User: Hello" in formatted
    assert "Assistant: Hi there" in formatted


@pytest.mark.asyncio
async def test_consolidate_extracts_and_stores_summary(
    mock_llm, mock_vector, consolidator
):
    mock_llm.complete.return_value = json.dumps(
        {
            "summary": "User asked about weather in Paris.",
            "facts": [],
            "entities": [],
        }
    )

    turns = [{"role": "user", "content": "What's the weather in Paris?"}]
    result = await consolidator.consolidate("session-123", turns)

    assert result["status"] == "success"
    assert result["summary"] == "User asked about weather in Paris."
    mock_vector.store.assert_called_once()


@pytest.mark.asyncio
async def test_consolidate_updates_preferences(
    mock_llm, mock_world_model, consolidator
):
    mock_llm.complete.return_value = json.dumps(
        {
            "summary": "User mentioned their location.",
            "facts": [{"type": "preference", "content": "location: Berlin"}],
            "entities": [],
        }
    )

    turns = [{"role": "user", "content": "I live in Berlin"}]
    result = await consolidator.consolidate("session-123", turns)

    mock_world_model.set_preference.assert_called_once_with("location", "Berlin")
    assert result["facts_count"] == 1


@pytest.mark.asyncio
async def test_consolidate_adds_entities_to_graph(mock_llm, mock_graph, consolidator):
    mock_llm.complete.return_value = json.dumps(
        {
            "summary": "User talked about a project.",
            "facts": [],
            "entities": [
                {
                    "name": "Project Alpha",
                    "type": "project",
                    "context": "User's main project",
                },
            ],
        }
    )

    turns = [{"role": "user", "content": "Working on Project Alpha"}]
    result = await consolidator.consolidate("session-123", turns)

    mock_graph.upsert_entity.assert_called_once_with(
        "Project Alpha",
        "project",
        "User's main project",
    )
    assert result["entities_count"] == 1


@pytest.mark.asyncio
async def test_consolidate_handles_json_in_markdown_code_block(mock_llm, consolidator):
    mock_llm.complete.return_value = """Here's the analysis:
```json
{
  "summary": "User discussed coding",
  "facts": [],
  "entities": []
}
```"""

    turns = [{"role": "user", "content": "Let's code"}]
    result = await consolidator.consolidate("session-123", turns)

    assert result["status"] == "success"
    assert result["summary"] == "User discussed coding"


@pytest.mark.asyncio
async def test_consolidate_handles_malformed_llm_response(mock_llm, consolidator):
    mock_llm.complete.return_value = "This is not valid JSON"

    turns = [{"role": "user", "content": "Hello"}]
    result = await consolidator.consolidate("session-123", turns)

    assert result["status"] == "success"
    assert result["summary"] == ""


@pytest.mark.asyncio
async def test_consolidate_processes_multiple_facts_and_entities(
    mock_llm, mock_world_model, mock_graph, consolidator
):
    mock_llm.complete.return_value = json.dumps(
        {
            "summary": "Rich conversation about preferences and entities.",
            "facts": [
                {"type": "preference", "content": "theme: dark"},
                {"type": "preference", "content": "language: Python"},
            ],
            "entities": [
                {"name": "Alice", "type": "person", "context": "User's colleague"},
                {"name": "Office", "type": "place", "context": "User works here"},
            ],
        }
    )

    turns = [{"role": "user", "content": "Complex conversation"}]
    result = await consolidator.consolidate("session-123", turns)

    assert result["facts_count"] == 2
    assert result["entities_count"] == 2
    assert mock_world_model.set_preference.call_count == 2
    assert mock_graph.upsert_entity.call_count == 2


@pytest.mark.asyncio
async def test_consolidate_ignores_non_preference_facts(
    mock_llm, mock_world_model, consolidator
):
    mock_llm.complete.return_value = json.dumps(
        {
            "summary": "User mentioned an event.",
            "facts": [
                {"type": "event", "content": "Birthday next week"},
                {"type": "habit", "content": "Runs every morning"},
            ],
            "entities": [],
        }
    )

    turns = [{"role": "user", "content": "My birthday is next week"}]
    result = await consolidator.consolidate("session-123", turns)

    mock_world_model.set_preference.assert_not_called()
    assert result["facts_count"] == 2


@pytest.mark.asyncio
async def test_consolidate_handles_missing_entity_context(
    mock_llm, mock_graph, consolidator
):
    mock_llm.complete.return_value = json.dumps(
        {
            "summary": "User mentioned a person.",
            "facts": [],
            "entities": [
                {"name": "Bob", "type": "person"},
            ],
        }
    )

    turns = [{"role": "user", "content": "Bob is my friend"}]
    result = await consolidator.consolidate("session-123", turns)

    mock_graph.upsert_entity.assert_called_once_with("Bob", "person", "")


@pytest.mark.asyncio
async def test_consolidate_ignores_preference_without_colon(
    mock_llm, mock_world_model, consolidator
):
    mock_llm.complete.return_value = json.dumps(
        {
            "summary": "User mentioned something.",
            "facts": [{"type": "preference", "content": "no colon here"}],
            "entities": [],
        }
    )

    turns = [{"role": "user", "content": "Some message"}]
    result = await consolidator.consolidate("session-123", turns)

    mock_world_model.set_preference.assert_not_called()
    assert result["facts_count"] == 1


@pytest.mark.asyncio
async def test_consolidate_ignores_empty_key_in_preference(
    mock_llm, mock_world_model, consolidator
):
    mock_llm.complete.return_value = json.dumps(
        {
            "summary": "User mentioned something.",
            "facts": [{"type": "preference", "content": ": value"}],
            "entities": [],
        }
    )

    turns = [{"role": "user", "content": "Some message"}]
    result = await consolidator.consolidate("session-123", turns)

    mock_world_model.set_preference.assert_not_called()


@pytest.mark.asyncio
async def test_consolidate_handles_invalid_fact_type(
    mock_llm, mock_world_model, consolidator
):
    mock_llm.complete.return_value = json.dumps(
        {
            "summary": "User mentioned something.",
            "facts": [{"type": "invalid_type", "content": "some content"}],
            "entities": [],
        }
    )

    turns = [{"role": "user", "content": "Some message"}]
    result = await consolidator.consolidate("session-123", turns)

    mock_world_model.set_preference.assert_not_called()
    assert result["facts_count"] == 1
