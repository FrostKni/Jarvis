import pytest
import pytest_asyncio
import os
import tempfile
import subprocess
from pathlib import Path
from backend.tools.registry import ToolExecutor, TOOL_DEFINITIONS


@pytest.fixture
def executor():
    return ToolExecutor(store=None)


class TestToolDefinitions:
    def test_developer_tools_in_definitions(self):
        tool_names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "execute_terminal" in tool_names
        assert "git_status" in tool_names
        assert "git_commit" in tool_names
        assert "git_push" in tool_names
        assert "search_code" in tool_names

    def test_execute_terminal_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "execute_terminal")
        props = tool["input_schema"]["properties"]
        assert "command" in props
        assert "cwd" in props
        assert "timeout" in props
        assert props["timeout"]["default"] == 30
        assert set(tool["input_schema"]["required"]) == {"command"}

    def test_git_status_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "git_status")
        props = tool["input_schema"]["properties"]
        assert "repo_path" in props
        assert tool["input_schema"]["required"] == []

    def test_git_commit_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "git_commit")
        props = tool["input_schema"]["properties"]
        assert "message" in props
        assert "repo_path" in props
        assert "add_all" in props
        assert props["add_all"]["default"] == False
        assert set(tool["input_schema"]["required"]) == {"message"}

    def test_git_push_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "git_push")
        props = tool["input_schema"]["properties"]
        assert "repo_path" in props
        assert "remote" in props
        assert "branch" in props
        assert props["remote"]["default"] == "origin"
        assert tool["input_schema"]["required"] == []

    def test_search_code_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "search_code")
        props = tool["input_schema"]["properties"]
        assert "directory" in props
        assert "pattern" in props
        assert "file_pattern" in props
        assert "context_lines" in props
        assert props["file_pattern"]["default"] == "*"
        assert props["context_lines"]["default"] == 2
        assert set(tool["input_schema"]["required"]) == {"directory", "pattern"}


class TestExecuteTerminal:
    @pytest.mark.asyncio
    async def test_execute_simple_command(self, executor):
        result = await executor.execute("execute_terminal", {"command": "echo hello"})
        assert "hello" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_command_with_cwd(self, executor):
        with tempfile.TemporaryDirectory() as d:
            result = await executor.execute(
                "execute_terminal", {"command": "pwd", "cwd": d}
            )
            assert d in result or result.strip() == d

    @pytest.mark.asyncio
    async def test_execute_command_timeout_default(self, executor):
        result = await executor.execute("execute_terminal", {"command": "echo test"})
        assert "test" in result.lower()

    @pytest.mark.asyncio
    async def test_blocks_dangerous_rm_rf_root(self, executor):
        result = await executor.execute("execute_terminal", {"command": "rm -rf /"})
        assert (
            "blocked" in result.lower()
            or "denied" in result.lower()
            or "dangerous" in result.lower()
        )

    @pytest.mark.asyncio
    async def test_blocks_dangerous_sudo(self, executor):
        result = await executor.execute("execute_terminal", {"command": "sudo rm test"})
        assert (
            "blocked" in result.lower()
            or "denied" in result.lower()
            or "dangerous" in result.lower()
        )

    @pytest.mark.asyncio
    async def test_blocks_dangerous_mkfs(self, executor):
        result = await executor.execute(
            "execute_terminal", {"command": "mkfs.ext4 /dev/sda1"}
        )
        assert (
            "blocked" in result.lower()
            or "denied" in result.lower()
            or "dangerous" in result.lower()
        )

    @pytest.mark.asyncio
    async def test_blocks_dangerous_dd(self, executor):
        result = await executor.execute(
            "execute_terminal", {"command": "dd if=/dev/zero of=/dev/sda"}
        )
        assert (
            "blocked" in result.lower()
            or "denied" in result.lower()
            or "dangerous" in result.lower()
        )

    @pytest.mark.asyncio
    async def test_command_stderr_captured(self, executor):
        result = await executor.execute(
            "execute_terminal", {"command": "ls /nonexistent_directory_xyz_12345"}
        )
        assert result

    @pytest.mark.asyncio
    async def test_output_truncated_at_5000_chars(self, executor):
        result = await executor.execute(
            "execute_terminal", {"command": "python3 -c \"print('x' * 10000)\""}
        )
        assert len(result) <= 5100


class TestGitStatus:
    @pytest.mark.asyncio
    async def test_git_status_in_repo(self, executor):
        result = await executor.execute("git_status", {})
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_git_status_specific_repo(self, executor):
        result = await executor.execute("git_status", {"repo_path": "."})
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_git_status_non_repo(self, executor):
        with tempfile.TemporaryDirectory() as d:
            result = await executor.execute("git_status", {"repo_path": d})
            assert "error" in result.lower() or "not a git" in result.lower()


class TestGitCommit:
    @pytest.mark.asyncio
    async def test_git_commit_requires_message(self, executor):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init"], cwd=d, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=d,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"], cwd=d, capture_output=True
            )
            Path(d, "test.txt").write_text("test")

            result = await executor.execute(
                "git_commit",
                {"message": "Test commit", "repo_path": d, "add_all": True},
            )
            assert "commit" in result.lower() or "nothing to commit" in result.lower()

    @pytest.mark.asyncio
    async def test_git_commit_without_add_all(self, executor):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init"], cwd=d, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=d,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"], cwd=d, capture_output=True
            )
            Path(d, "test.txt").write_text("test")

            result = await executor.execute(
                "git_commit",
                {"message": "Test commit", "repo_path": d, "add_all": False},
            )
            assert isinstance(result, str)


class TestGitPush:
    @pytest.mark.asyncio
    async def test_git_push_no_remote(self, executor):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init"], cwd=d, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=d,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"], cwd=d, capture_output=True
            )

            result = await executor.execute("git_push", {"repo_path": d})
            assert (
                "error" in result.lower()
                or "no remote" in result.lower()
                or "push" in result.lower()
            )

    @pytest.mark.asyncio
    async def test_git_push_with_remote_param(self, executor):
        result = await executor.execute("git_push", {"remote": "origin"})
        assert isinstance(result, str)


class TestSearchCode:
    @pytest.mark.asyncio
    async def test_search_code_finds_match(self, executor):
        with tempfile.TemporaryDirectory() as d:
            test_file = Path(d, "test.py")
            test_file.write_text("def hello_world():\n    print('hello')\n")

            result = await executor.execute(
                "search_code", {"directory": d, "pattern": "hello"}
            )
            assert "hello" in result.lower() or "test.py" in result

    @pytest.mark.asyncio
    async def test_search_code_no_match(self, executor):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "test.py").write_text("def foo():\n    pass\n")

            result = await executor.execute(
                "search_code", {"directory": d, "pattern": "nonexistent_pattern_xyz"}
            )
            assert (
                "no match" in result.lower()
                or "not found" in result.lower()
                or result == ""
            )

    @pytest.mark.asyncio
    async def test_search_code_with_file_pattern(self, executor):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "test.py").write_text("python_code = 1\n")
            Path(d, "test.txt").write_text("python_code = 2\n")

            result = await executor.execute(
                "search_code",
                {"directory": d, "pattern": "python_code", "file_pattern": "*.py"},
            )
            assert "test.py" in result
            assert "test.txt" not in result

    @pytest.mark.asyncio
    async def test_search_code_invalid_directory(self, executor):
        result = await executor.execute(
            "search_code", {"directory": "/nonexistent/path", "pattern": "test"}
        )
        assert "error" in result.lower() or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_search_code_with_context_lines(self, executor):
        with tempfile.TemporaryDirectory() as d:
            test_file = Path(d, "test.py")
            test_file.write_text("line1\nline2\nmatch_here\nline4\nline5\n")

            result = await executor.execute(
                "search_code",
                {"directory": d, "pattern": "match_here", "context_lines": 1},
            )
            assert "match_here" in result
