import pytest
import asyncio
from backend.proactive.workflow_orchestrator import (
    WorkflowOrchestrator,
    WorkflowStatus,
    Workflow,
    WorkflowStep,
)


@pytest.fixture
def orchestrator():
    return WorkflowOrchestrator()


@pytest.mark.asyncio
async def test_create_workflow(orchestrator):
    steps = [
        {"action_type": "read_file", "parameters": {"path": "/tmp/test.txt"}},
        {"action_type": "web_search", "parameters": {"query": "test"}},
    ]

    workflow = await orchestrator.create_workflow(name="test_workflow", steps=steps)

    assert workflow.workflow_id is not None
    assert workflow.name == "test_workflow"
    assert len(workflow.steps) == 2
    assert workflow.status == WorkflowStatus.PENDING


@pytest.mark.asyncio
async def test_execute_workflow_no_handler(orchestrator):
    steps = [{"action_type": "unknown_action", "parameters": {}}]

    workflow = await orchestrator.create_workflow(name="test", steps=steps)
    result = await orchestrator.execute_workflow(workflow.workflow_id)

    assert result["success"] is False
    assert "failed" in result["error"].lower() or "handler" in result["error"].lower()


@pytest.mark.asyncio
async def test_execute_workflow_with_handler(orchestrator):
    async def mock_handler(params):
        return "success"

    orchestrator.register_step_handler("mock_action", mock_handler)

    steps = [{"action_type": "mock_action", "parameters": {}}]

    workflow = await orchestrator.create_workflow(name="test", steps=steps)
    result = await orchestrator.execute_workflow(workflow.workflow_id)

    assert result["success"] is True


@pytest.mark.asyncio
async def test_get_workflow_status(orchestrator):
    steps = [{"action_type": "test", "parameters": {}}]

    workflow = await orchestrator.create_workflow(name="test", steps=steps)
    status = await orchestrator.get_workflow_status(workflow.workflow_id)

    assert status is not None
    assert status["workflow_id"] == workflow.workflow_id
    assert status["name"] == "test"
    assert status["status"] == "pending"


@pytest.mark.asyncio
async def test_get_workflow_status_not_found(orchestrator):
    status = await orchestrator.get_workflow_status("nonexistent")
    assert status is None


@pytest.mark.asyncio
async def test_pause_workflow(orchestrator):
    steps = [{"action_type": "test", "parameters": {}}]
    workflow = await orchestrator.create_workflow(name="test", steps=steps)
    workflow.status = WorkflowStatus.RUNNING

    result = await orchestrator.pause_workflow(workflow.workflow_id)
    assert result is True
    assert workflow.status == WorkflowStatus.PAUSED


@pytest.mark.asyncio
async def test_resume_workflow(orchestrator):
    steps = [{"action_type": "test", "parameters": {}}]
    workflow = await orchestrator.create_workflow(name="test", steps=steps)
    workflow.status = WorkflowStatus.PAUSED

    result = await orchestrator.resume_workflow(workflow.workflow_id)
    assert result is True


@pytest.mark.asyncio
async def test_cancel_workflow(orchestrator):
    steps = [{"action_type": "test", "parameters": {}}]
    workflow = await orchestrator.create_workflow(name="test", steps=steps)

    result = await orchestrator.cancel_workflow(workflow.workflow_id)
    assert result is True
    assert workflow.status == WorkflowStatus.FAILED


@pytest.mark.asyncio
async def test_list_workflows(orchestrator):
    steps = [{"action_type": "test", "parameters": {}}]
    await orchestrator.create_workflow(name="workflow1", steps=steps)
    await orchestrator.create_workflow(name="workflow2", steps=steps)

    workflows = await orchestrator.list_workflows()
    assert len(workflows) == 2


@pytest.mark.asyncio
async def test_list_workflows_filter_by_status(orchestrator):
    steps = [{"action_type": "test", "parameters": {}}]
    await orchestrator.create_workflow(name="pending", steps=steps)

    workflow2 = await orchestrator.create_workflow(name="completed", steps=steps)
    workflow2.status = WorkflowStatus.COMPLETED

    pending = await orchestrator.list_workflows(status=WorkflowStatus.PENDING)
    assert len(pending) == 1
    assert pending[0]["name"] == "pending"


@pytest.mark.asyncio
async def test_cleanup_completed(orchestrator):
    steps = [{"action_type": "test", "parameters": {}}]

    workflow = await orchestrator.create_workflow(name="old", steps=steps)
    workflow.status = WorkflowStatus.COMPLETED
    workflow.completed_at = workflow.created_at - __import__("datetime").timedelta(
        hours=48
    )

    cleaned = await orchestrator.cleanup_completed(max_age_hours=24)
    assert cleaned == 1


@pytest.mark.asyncio
async def test_max_concurrent_workflows():
    orch = WorkflowOrchestrator()
    orch._max_concurrent_workflows = 1

    async def slow_handler(params):
        await asyncio.sleep(0.1)
        return "done"

    orch.register_step_handler("slow", slow_handler)

    steps = [{"action_type": "slow", "parameters": {}}]

    w1 = await orch.create_workflow(name="w1", steps=steps)
    w2 = await orch.create_workflow(name="w2", steps=steps)

    task1 = asyncio.create_task(orch.execute_workflow(w1.workflow_id))
    await asyncio.sleep(0.01)

    result2 = await orch.execute_workflow(w2.workflow_id)
    assert result2["success"] is False
    assert "max concurrent" in result2["error"].lower()

    await task1
