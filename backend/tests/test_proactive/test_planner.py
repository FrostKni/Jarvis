import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from backend.proactive.planner import MultiStepPlanner, PlanStep, ExecutionPlan


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.complete = AsyncMock()
    return llm


@pytest.fixture
def planner(mock_llm):
    return MultiStepPlanner(llm=mock_llm)


@pytest.mark.asyncio
async def test_create_plan_simple(planner, mock_llm):
    mock_response = json.dumps(
        {
            "steps": [
                {
                    "step_number": 1,
                    "action": "web_search",
                    "description": "Search for information",
                    "parameters": {"query": "test"},
                    "dependencies": [],
                }
            ],
            "reasoning": "Simple search task",
        }
    )
    mock_llm.complete.return_value = mock_response

    plan = await planner.create_plan(goal="Find information about test")

    assert plan.goal == "Find information about test"
    assert len(plan.steps) == 1
    assert plan.steps[0].action == "web_search"
    assert plan.reasoning == "Simple search task"


@pytest.mark.asyncio
async def test_create_plan_multi_step(planner, mock_llm):
    mock_response = json.dumps(
        {
            "steps": [
                {
                    "step_number": 1,
                    "action": "read_file",
                    "description": "Read the config",
                    "parameters": {"path": "/etc/config"},
                    "dependencies": [],
                },
                {
                    "step_number": 2,
                    "action": "web_search",
                    "description": "Search for updates",
                    "parameters": {"query": "updates"},
                    "dependencies": [1],
                },
            ],
            "reasoning": "Sequential dependency chain",
        }
    )
    mock_llm.complete.return_value = mock_response

    plan = await planner.create_plan(goal="Update configuration")

    assert len(plan.steps) == 2
    assert plan.steps[1].dependencies == [1]


@pytest.mark.asyncio
async def test_create_plan_with_context(planner, mock_llm):
    mock_llm.complete.return_value = json.dumps(
        {"steps": [], "reasoning": "Empty plan"}
    )

    await planner.create_plan(
        goal="Test goal", context={"user": "test_user", "environment": "dev"}
    )

    call_args = mock_llm.complete.call_args
    assert "context" in str(call_args).lower() or "test_user" in str(call_args)


@pytest.mark.asyncio
async def test_parse_plan_from_text(planner):
    text_response = """1. First search for information
2. Then read the relevant file
3. Finally execute the command"""

    result = planner._parse_plan_from_text(text_response)

    assert len(result["steps"]) == 3
    assert result["steps"][0]["step_number"] == 1
    assert "search" in result["steps"][0]["description"].lower()


@pytest.mark.asyncio
async def test_infer_action_from_description(planner):
    assert (
        planner._infer_action_from_description("Search for Python tutorials")
        == "web_search"
    )
    assert planner._infer_action_from_description("Read the config file") == "read_file"
    assert (
        planner._infer_action_from_description("Write results to output.txt")
        == "write_file"
    )
    assert (
        planner._infer_action_from_description("Run the script") == "execute_terminal"
    )
    assert planner._infer_action_from_description("Send email to team") == "send_email"


@pytest.mark.asyncio
async def test_refine_plan(planner, mock_llm):
    original_plan = ExecutionPlan(
        goal="Test goal",
        steps=[
            PlanStep(
                step_number=1,
                action="web_search",
                description="Search",
                parameters={},
                dependencies=[],
            )
        ],
        estimated_actions=1,
        reasoning="Original plan",
    )

    mock_llm.complete.return_value = json.dumps(
        {
            "steps": [
                {
                    "step_number": 1,
                    "action": "web_search",
                    "description": "Enhanced search",
                    "parameters": {"query": "refined"},
                    "dependencies": [],
                }
            ],
            "reasoning": "Refined based on feedback",
        }
    )

    refined = await planner.refine_plan(original_plan, "Use more specific query")

    assert refined.goal == original_plan.goal
    assert "Refined" in refined.reasoning


@pytest.mark.asyncio
async def test_estimate_complexity(planner, mock_llm):
    mock_llm.complete.return_value = json.dumps(
        {
            "steps": [
                {
                    "step_number": 1,
                    "action": "read_file",
                    "description": "Read",
                    "parameters": {},
                    "dependencies": [],
                },
                {
                    "step_number": 2,
                    "action": "web_search",
                    "description": "Search",
                    "parameters": {},
                    "dependencies": [],
                },
                {
                    "step_number": 3,
                    "action": "write_file",
                    "description": "Write",
                    "parameters": {},
                    "dependencies": [],
                },
            ],
            "reasoning": "Three step process",
        }
    )

    complexity = await planner.estimate_complexity("Do something complex")

    assert complexity["estimated_steps"] == 3
    assert complexity["complexity"] == "medium"
    assert complexity["estimated_time_minutes"] == 6


@pytest.mark.asyncio
async def test_format_plan_for_display(planner):
    plan = ExecutionPlan(
        goal="Test goal",
        steps=[
            PlanStep(
                step_number=1,
                action="web_search",
                description="Search for info",
                parameters={"query": "test"},
                dependencies=[],
            )
        ],
        estimated_actions=1,
        reasoning="Test reasoning",
    )

    formatted = planner.format_plan_for_display(plan)

    assert "Test goal" in formatted
    assert "web_search" in formatted
    assert "Search for info" in formatted
    assert "Test reasoning" in formatted


@pytest.mark.asyncio
async def test_create_plan_invalid_json(planner, mock_llm):
    mock_llm.complete.return_value = "1. First step\n2. Second step"

    plan = await planner.create_plan(goal="Test")

    assert len(plan.steps) == 2
    assert plan.steps[0].step_number == 1
