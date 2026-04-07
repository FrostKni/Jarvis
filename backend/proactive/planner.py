import json
from typing import Optional
from dataclasses import dataclass
from backend.brain.llm import LLMClient


@dataclass
class PlanStep:
    step_number: int
    action: str
    description: str
    parameters: dict
    dependencies: list[int]


@dataclass
class ExecutionPlan:
    goal: str
    steps: list[PlanStep]
    estimated_actions: int
    reasoning: str


PLANNING_SYSTEM = """You are a strategic planning assistant. Your role is to break down high-level goals into actionable steps.
Each step should be a single, atomic action that can be executed using available tools.

Available action types:
- web_search: Search for information online
- read_file: Read a file from the filesystem
- write_file: Write content to a file
- execute_terminal: Run a terminal command
- send_email: Send an email
- navigate_url: Navigate to a URL
- http_request: Make an HTTP API request

Guidelines:
1. Break complex goals into 3-7 concrete steps
2. Each step should have clear, actionable parameters
3. Consider dependencies between steps
4. Provide brief reasoning for the plan structure

Respond with a JSON object containing:
{
  "steps": [
    {
      "step_number": 1,
      "action": "action_type",
      "description": "What this step accomplishes",
      "parameters": {"key": "value"},
      "dependencies": []
    }
  ],
  "reasoning": "Brief explanation of the plan approach"
}"""


class MultiStepPlanner:
    def __init__(self, llm: Optional[LLMClient] = None):
        self._llm = llm or LLMClient()

    async def create_plan(self, goal: str, context: dict = None) -> ExecutionPlan:
        context_str = ""
        if context:
            context_str = f"\n\nContext:\n{json.dumps(context, indent=2)}"

        messages = [
            {
                "role": "user",
                "content": f"Create an execution plan for the following goal:\n\n{goal}{context_str}",
            }
        ]

        response = await self._llm.complete(messages=messages, system=PLANNING_SYSTEM)

        try:
            plan_data = json.loads(response)
        except json.JSONDecodeError:
            plan_data = self._parse_plan_from_text(response)

        steps = []
        for step_data in plan_data.get("steps", []):
            step = PlanStep(
                step_number=step_data.get("step_number", len(steps) + 1),
                action=step_data.get("action", "unknown"),
                description=step_data.get("description", ""),
                parameters=step_data.get("parameters", {}),
                dependencies=step_data.get("dependencies", []),
            )
            steps.append(step)

        return ExecutionPlan(
            goal=goal,
            steps=steps,
            estimated_actions=len(steps),
            reasoning=plan_data.get("reasoning", "Plan generated from goal analysis"),
        )

    def _parse_plan_from_text(self, text: str) -> dict:
        steps = []
        lines = text.split("\n")
        step_num = 0

        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                step_num += 1
                description = line.lstrip("0123456789.- ").strip()
                action = self._infer_action_from_description(description)
                steps.append(
                    {
                        "step_number": step_num,
                        "action": action,
                        "description": description,
                        "parameters": {},
                        "dependencies": [],
                    }
                )

        return {"steps": steps, "reasoning": "Parsed from text response"}

    def _infer_action_from_description(self, description: str) -> str:
        desc_lower = description.lower()

        if any(word in desc_lower for word in ["search", "find", "look up", "google"]):
            return "web_search"
        elif any(word in desc_lower for word in ["read", "open", "view"]):
            return "read_file"
        elif any(word in desc_lower for word in ["write", "create", "save"]):
            return "write_file"
        elif any(word in desc_lower for word in ["run", "execute", "command"]):
            return "execute_terminal"
        elif any(word in desc_lower for word in ["email", "send", "mail"]):
            return "send_email"
        elif any(word in desc_lower for word in ["navigate", "go to", "open url"]):
            return "navigate_url"
        elif any(word in desc_lower for word in ["request", "api", "http"]):
            return "http_request"
        else:
            return "execute_terminal"

    async def refine_plan(self, plan: ExecutionPlan, feedback: str) -> ExecutionPlan:
        messages = [
            {
                "role": "user",
                "content": f"Original goal: {plan.goal}\n\nCurrent plan:\n{json.dumps([{'step': s.step_number, 'action': s.action, 'description': s.description} for s in plan.steps], indent=2)}\n\nFeedback/adjustment needed:\n{feedback}\n\nProvide an updated plan.",
            }
        ]

        response = await self._llm.complete(messages=messages, system=PLANNING_SYSTEM)

        try:
            plan_data = json.loads(response)
        except json.JSONDecodeError:
            plan_data = self._parse_plan_from_text(response)

        steps = []
        for step_data in plan_data.get("steps", []):
            step = PlanStep(
                step_number=step_data.get("step_number", len(steps) + 1),
                action=step_data.get("action", "unknown"),
                description=step_data.get("description", ""),
                parameters=step_data.get("parameters", {}),
                dependencies=step_data.get("dependencies", []),
            )
            steps.append(step)

        return ExecutionPlan(
            goal=plan.goal,
            steps=steps,
            estimated_actions=len(steps),
            reasoning=f"Refined based on feedback: {feedback}",
        )

    async def estimate_complexity(self, goal: str) -> dict:
        plan = await self.create_plan(goal)

        return {
            "estimated_steps": len(plan.steps),
            "complexity": "low"
            if len(plan.steps) <= 2
            else "medium"
            if len(plan.steps) <= 5
            else "high",
            "estimated_time_minutes": len(plan.steps) * 2,
            "required_actions": list(set(s.action for s in plan.steps)),
        }

    def format_plan_for_display(self, plan: ExecutionPlan) -> str:
        lines = [f"Goal: {plan.goal}", "", "Steps:"]

        for step in plan.steps:
            deps = (
                f" (depends on steps: {step.dependencies})" if step.dependencies else ""
            )
            lines.append(
                f"  {step.step_number}. [{step.action}] {step.description}{deps}"
            )
            if step.parameters:
                for key, value in step.parameters.items():
                    lines.append(f"     - {key}: {value}")

        lines.append("")
        lines.append(f"Reasoning: {plan.reasoning}")

        return "\n".join(lines)
