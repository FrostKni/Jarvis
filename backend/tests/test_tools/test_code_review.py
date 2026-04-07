import pytest
from backend.tools.registry import ToolExecutor, TOOL_DEFINITIONS


@pytest.fixture
def executor():
    return ToolExecutor(store=None)


class TestToolDefinitions:
    def test_code_review_tools_in_definitions(self):
        tool_names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "analyze_code" in tool_names
        assert "suggest_improvements" in tool_names

    def test_analyze_code_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "analyze_code")
        props = tool["input_schema"]["properties"]
        assert "code" in props
        assert "language" in props
        assert "checks" in props
        assert props["language"]["default"] == "python"
        assert set(tool["input_schema"]["required"]) == {"code"}

    def test_suggest_improvements_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "suggest_improvements")
        props = tool["input_schema"]["properties"]
        assert "code" in props
        assert "language" in props
        assert "focus" in props
        assert props["language"]["default"] == "python"
        assert set(tool["input_schema"]["required"]) == {"code"}


class TestAnalyzeCode:
    @pytest.mark.asyncio
    async def test_analyze_clean_code(self, executor):
        code = "def hello():\n    return 'world'\n"
        result = await executor.execute("analyze_code", {"code": code})
        assert result
        import json

        data = json.loads(result)
        assert "issues" in data

    @pytest.mark.asyncio
    async def test_analyze_syntax_error(self, executor):
        code = "def broken(\n"
        result = await executor.execute("analyze_code", {"code": code})
        import json

        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_analyze_dangerous_function_eval(self, executor):
        code = "x = eval(user_input)\n"
        result = await executor.execute(
            "analyze_code", {"code": code, "checks": ["security"]}
        )
        import json

        data = json.loads(result)
        assert any(
            "eval" in issue.get("message", "") for issue in data.get("issues", [])
        )

    @pytest.mark.asyncio
    async def test_analyze_dangerous_function_exec(self, executor):
        code = "exec(code_string)\n"
        result = await executor.execute(
            "analyze_code", {"code": code, "checks": ["security"]}
        )
        import json

        data = json.loads(result)
        assert any(
            "exec" in issue.get("message", "") for issue in data.get("issues", [])
        )

    @pytest.mark.asyncio
    async def test_analyze_unused_import(self, executor):
        code = "import os\n\ndef foo():\n    pass\n"
        result = await executor.execute(
            "analyze_code", {"code": code, "checks": ["lint"]}
        )
        import json

        data = json.loads(result)
        lint_issues = [i for i in data.get("issues", []) if i.get("type") == "lint"]
        assert any("os" in i.get("message", "") for i in lint_issues)

    @pytest.mark.asyncio
    async def test_analyze_specific_checks(self, executor):
        code = "def hello():\n    return 'world'\n"
        result = await executor.execute(
            "analyze_code", {"code": code, "checks": ["lint"]}
        )
        import json

        data = json.loads(result)
        assert "issues" in data

    @pytest.mark.asyncio
    async def test_analyze_unsupported_language(self, executor):
        code = "function test() { return 1; }"
        result = await executor.execute(
            "analyze_code", {"code": code, "language": "javascript"}
        )
        import json

        data = json.loads(result)
        assert any(
            "not yet supported" in issue.get("message", "")
            for issue in data.get("issues", [])
        )


class TestSuggestImprovements:
    @pytest.mark.asyncio
    async def test_suggest_improvements_returns_string(self, executor):
        code = "def foo():\n    pass\n"
        result = await executor.execute("suggest_improvements", {"code": code})
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_suggest_improvements_with_focus(self, executor):
        code = "def foo():\n    pass\n"
        result = await executor.execute(
            "suggest_improvements", {"code": code, "focus": "performance"}
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_suggest_improvements_with_language(self, executor):
        code = "function test() { return 1; }"
        result = await executor.execute(
            "suggest_improvements", {"code": code, "language": "javascript"}
        )
        assert isinstance(result, str)
