import json
from typing import AsyncGenerator
from backend.brain.llm import LLMClient
from backend.brain.router import IntentRouter
from backend.memory.assembler import MemoryAssembler
from backend.memory.session import SessionCache
from backend.memory.vector import VectorMemory
from backend.tools.registry import ToolExecutor, TOOL_DEFINITIONS

JARVIS_SYSTEM = """You are Jarvis, an advanced AI assistant. You are precise, proactive, and efficient.
You have access to tools to take real actions. Use them when needed.
Always be concise — you are speaking aloud, so avoid markdown, bullet points, or long lists.
{memory_context}"""


class JarvisOrchestrator:
    def __init__(
        self,
        llm: LLMClient,
        router: IntentRouter,
        assembler: MemoryAssembler,
        session: SessionCache,
        vector: VectorMemory,
        executor: ToolExecutor,
    ):
        self.llm = llm
        self.router = router
        self.assembler = assembler
        self.session = session
        self.vector = vector
        self.executor = executor

    async def process(self, session_id: str, user_text: str) -> AsyncGenerator[str, None]:
        # 1. Route intent
        intent = await self.router.route(user_text)

        # 2. Build memory context
        memory_ctx = await self.assembler.build_context(user_text)
        system = JARVIS_SYSTEM.format(memory_context=f"\n\n{memory_ctx}" if memory_ctx else "")

        # 3. Get conversation history
        history = await self.session.get_turns(session_id)
        messages = history + [{"role": "user", "content": user_text}]

        # 4. Store user turn
        await self.session.add_turn(session_id, "user", user_text)

        # 5. Agentic loop with tools if needed
        if intent.get("needs_tools"):
            response_text = await self._agentic_loop(messages, system)
            yield response_text
        else:
            # 6. Stream response
            full_response = ""
            async for token in self.llm.stream(
                messages=messages,
                system=system,
                fast=(intent.get("complexity") == "fast"),
            ):
                full_response += token
                yield token
            response_text = full_response

        # 7. Store assistant turn and memory
        await self.session.add_turn(session_id, "assistant", response_text)
        self.vector.store(f"User: {user_text}\nJarvis: {response_text}")

    async def _agentic_loop(self, messages: list[dict], system: str) -> str:
        max_iterations = 5
        for _ in range(max_iterations):
            response = await self.llm.complete_with_tools(messages, TOOL_DEFINITIONS, system)

            if response.stop_reason == "end_turn":
                return response.content[0].text if response.content else ""

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = await self.executor.execute(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                messages = messages + [
                    {"role": "assistant", "content": response.content},
                    {"role": "user", "content": tool_results},
                ]
            else:
                break

        return "I encountered an issue completing that task."
