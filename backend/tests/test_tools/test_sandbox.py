import pytest
from backend.tools.sandbox import CodeSandbox, DOCKER_AVAILABLE
from backend.tools.registry import ToolExecutor, TOOL_DEFINITIONS


@pytest.fixture
def sandbox():
    return CodeSandbox()


@pytest.fixture
def executor():
    return ToolExecutor(store=None)


class TestSandboxToolDefinition:
    def test_sandbox_tool_in_definitions(self):
        tool_names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "execute_code_sandbox" in tool_names

    def test_sandbox_tool_schema(self):
        tool = next(
            (t for t in TOOL_DEFINITIONS if t["name"] == "execute_code_sandbox"), None
        )
        assert tool is not None
        props = tool["input_schema"]["properties"]
        assert "code" in props
        assert "language" in props
        assert "timeout" in props
        assert props["language"]["default"] == "python"
        assert props["timeout"]["default"] == 30
        assert set(tool["input_schema"]["required"]) == {"code"}


class TestCodeSandbox:
    def test_sandbox_initialization(self, sandbox):
        assert sandbox is not None
        assert sandbox.DEFAULT_IMAGE == "python:3.11-slim"
        assert sandbox.CPU_LIMIT == 1.0
        assert sandbox.MEMORY_LIMIT == "256m"
        assert sandbox.TIMEOUT == 30

    def test_language_images_mapping(self, sandbox):
        assert "python" in sandbox.LANGUAGE_IMAGES
        assert "javascript" in sandbox.LANGUAGE_IMAGES
        assert "bash" in sandbox.LANGUAGE_IMAGES

        python_img, python_cmd = sandbox.LANGUAGE_IMAGES["python"]
        assert python_img == "python:3.11-slim"
        assert python_cmd == ["python", "-c"]

        js_img, js_cmd = sandbox.LANGUAGE_IMAGES["javascript"]
        assert js_img == "node:20-slim"
        assert js_cmd == ["node", "-e"]

        bash_img, bash_cmd = sandbox.LANGUAGE_IMAGES["bash"]
        assert bash_img == "bash:5"
        assert bash_cmd == ["bash", "-c"]

    def test_get_image_and_command_defaults_to_python(self, sandbox):
        img, cmd = sandbox._get_image_and_command("unknown_language")
        assert img == "python:3.11-slim"
        assert cmd == ["python", "-c"]

    @pytest.mark.asyncio
    async def test_execute_returns_dict_structure(self, sandbox):
        result = await sandbox.execute("print('hello')", language="python")
        assert isinstance(result, dict)
        assert "success" in result
        assert "stdout" in result
        assert "stderr" in result
        assert "exit_code" in result
        assert "execution_time" in result

    @pytest.mark.asyncio
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available")
    async def test_execute_python_code(self, sandbox):
        result = await sandbox.execute("print('hello world')", language="python")
        assert result["success"] is True
        assert "hello world" in result["stdout"]
        assert result["exit_code"] == 0

    @pytest.mark.asyncio
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available")
    async def test_execute_python_with_error(self, sandbox):
        result = await sandbox.execute("1/0", language="python")
        assert result["success"] is False
        assert result["exit_code"] != 0
        assert (
            "ZeroDivisionError" in result["stderr"]
            or "error" in result["stderr"].lower()
        )

    @pytest.mark.asyncio
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available")
    async def test_execute_javascript_code(self, sandbox):
        result = await sandbox.execute("console.log('js test')", language="javascript")
        assert result["success"] is True
        assert "js test" in result["stdout"]

    @pytest.mark.asyncio
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available")
    async def test_execute_bash_code(self, sandbox):
        result = await sandbox.execute("echo 'bash test'", language="bash")
        assert result["success"] is True
        assert "bash test" in result["stdout"]

    @pytest.mark.asyncio
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available")
    async def test_timeout_enforcement(self, sandbox):
        import time

        start = time.time()
        result = await sandbox.execute(
            "import time; time.sleep(60)", language="python", timeout=5
        )
        elapsed = time.time() - start

        assert elapsed < 15
        assert result["success"] is False or "timeout" in result["stderr"].lower()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available")
    async def test_memory_limit_enforced(self, sandbox):
        result = await sandbox.execute(
            "x = 'a' * 500_000_000", language="python", memory_limit="64m"
        )
        assert result["success"] is False or result["exit_code"] != 0

    @pytest.mark.asyncio
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available")
    async def test_output_truncation(self, sandbox):
        result = await sandbox.execute(f"print('x' * 20000)", language="python")
        assert len(result["stdout"]) <= sandbox.MAX_OUTPUT + 100

    @pytest.mark.asyncio
    async def test_docker_not_available_graceful_error(self, sandbox):
        if DOCKER_AVAILABLE:
            pytest.skip("Docker is available, skipping graceful error test")

        result = await sandbox.execute("print('test')", language="python")
        assert result["success"] is False
        assert (
            "not installed" in result["error"].lower()
            or "docker" in result["error"].lower()
        )


class TestToolExecutorIntegration:
    @pytest.mark.asyncio
    async def test_executor_has_sandbox_handler(self, executor):
        assert "execute_code_sandbox" in executor._handlers

    @pytest.mark.asyncio
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available")
    async def test_executor_sandbox_python(self, executor):
        result = await executor.execute(
            "execute_code_sandbox", {"code": "print('integration test')"}
        )
        assert "integration test" in result
        assert "Exit code" in result

    @pytest.mark.asyncio
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available")
    async def test_executor_sandbox_with_language(self, executor):
        result = await executor.execute(
            "execute_code_sandbox",
            {"code": "console.log('js integration')", "language": "javascript"},
        )
        assert "js integration" in result

    @pytest.mark.asyncio
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker not available")
    async def test_executor_sandbox_with_custom_timeout(self, executor):
        result = await executor.execute(
            "execute_code_sandbox",
            {"code": "print('timeout test')", "timeout": 10},
        )
        assert "timeout test" in result

    @pytest.mark.asyncio
    async def test_executor_sandbox_error_handling(self, executor):
        result = await executor.execute(
            "execute_code_sandbox", {"code": "raise ValueError('test error')"}
        )
        assert "ValueError" in result or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_executor_sandbox_no_output(self, executor):
        if not DOCKER_AVAILABLE:
            pytest.skip("Docker not available")
        result = await executor.execute("execute_code_sandbox", {"code": "x = 1 + 1"})
        assert "no output" in result.lower() or "Exit code" in result
