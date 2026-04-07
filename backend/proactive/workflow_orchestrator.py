import asyncio
from datetime import datetime, timedelta
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid


class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class WorkflowStep:
    step_id: str
    action_type: str
    parameters: dict
    status: WorkflowStatus = WorkflowStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class Workflow:
    workflow_id: str
    name: str
    steps: list[WorkflowStep]
    current_step: int = 0
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)


class WorkflowOrchestrator:
    def __init__(self, tool_executor: Any = None):
        self._workflows: dict[str, Workflow] = {}
        self._tool_executor = tool_executor
        self._step_handlers: dict[str, Callable] = {}
        self._max_concurrent_workflows = 5
        self._active_count = 0

    def register_step_handler(self, action_type: str, handler: Callable) -> None:
        self._step_handlers[action_type] = handler

    async def create_workflow(
        self, name: str, steps: list[dict], metadata: dict = None
    ) -> Workflow:
        workflow_id = str(uuid.uuid4())[:8]

        workflow_steps = []
        for i, step_data in enumerate(steps):
            step = WorkflowStep(
                step_id=f"{workflow_id}_step_{i}",
                action_type=step_data["action_type"],
                parameters=step_data.get("parameters", {}),
            )
            workflow_steps.append(step)

        workflow = Workflow(
            workflow_id=workflow_id,
            name=name,
            steps=workflow_steps,
            metadata=metadata or {},
        )
        self._workflows[workflow_id] = workflow
        return workflow

    async def execute_workflow(self, workflow_id: str) -> dict:
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return {"success": False, "error": "Workflow not found"}

        if workflow.status == WorkflowStatus.RUNNING:
            return {"success": False, "error": "Workflow already running"}

        if self._active_count >= self._max_concurrent_workflows:
            return {"success": False, "error": "Max concurrent workflows reached"}

        workflow.status = WorkflowStatus.RUNNING
        self._active_count += 1

        try:
            for i, step in enumerate(workflow.steps):
                workflow.current_step = i
                step.status = WorkflowStatus.RUNNING

                try:
                    result = await self._execute_step(step)
                    step.result = result
                    step.status = WorkflowStatus.COMPLETED
                except Exception as e:
                    step.error = str(e)
                    step.status = WorkflowStatus.FAILED
                    workflow.status = WorkflowStatus.FAILED
                    return {
                        "success": False,
                        "error": f"Step {i} failed: {e}",
                        "workflow_id": workflow_id,
                    }

            workflow.status = WorkflowStatus.COMPLETED
            workflow.completed_at = datetime.now()
            return {
                "success": True,
                "workflow_id": workflow_id,
                "result": "All steps completed",
            }
        finally:
            self._active_count -= 1

    async def _execute_step(self, step: WorkflowStep) -> str:
        handler = self._step_handlers.get(step.action_type)

        if handler:
            return await handler(step.parameters)
        elif self._tool_executor:
            return await self._tool_executor.execute(step.action_type, step.parameters)
        else:
            raise ValueError(f"No handler for action type: {step.action_type}")

    async def get_workflow_status(self, workflow_id: str) -> Optional[dict]:
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return None

        return {
            "workflow_id": workflow.workflow_id,
            "name": workflow.name,
            "status": workflow.status.value,
            "current_step": workflow.current_step,
            "total_steps": len(workflow.steps),
            "steps": [
                {
                    "step_id": s.step_id,
                    "action_type": s.action_type,
                    "status": s.status.value,
                    "result": s.result,
                    "error": s.error,
                }
                for s in workflow.steps
            ],
            "created_at": workflow.created_at.isoformat(),
            "completed_at": workflow.completed_at.isoformat()
            if workflow.completed_at
            else None,
        }

    async def pause_workflow(self, workflow_id: str) -> bool:
        workflow = self._workflows.get(workflow_id)
        if not workflow or workflow.status != WorkflowStatus.RUNNING:
            return False

        workflow.status = WorkflowStatus.PAUSED
        return True

    async def resume_workflow(self, workflow_id: str) -> bool:
        workflow = self._workflows.get(workflow_id)
        if not workflow or workflow.status != WorkflowStatus.PAUSED:
            return False

        workflow.status = WorkflowStatus.PENDING
        return True

    async def cancel_workflow(self, workflow_id: str) -> bool:
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return False

        workflow.status = WorkflowStatus.FAILED
        return True

    async def list_workflows(self, status: WorkflowStatus = None) -> list[dict]:
        workflows = list(self._workflows.values())

        if status:
            workflows = [w for w in workflows if w.status == status]

        return [
            {
                "workflow_id": w.workflow_id,
                "name": w.name,
                "status": w.status.value,
                "step_count": len(w.steps),
                "created_at": w.created_at.isoformat(),
            }
            for w in workflows
        ]

    async def cleanup_completed(self, max_age_hours: int = 24) -> int:
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        to_remove = []

        for workflow_id, workflow in self._workflows.items():
            if workflow.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
                if workflow.completed_at and workflow.completed_at < cutoff:
                    to_remove.append(workflow_id)

        for workflow_id in to_remove:
            del self._workflows[workflow_id]

        return len(to_remove)
