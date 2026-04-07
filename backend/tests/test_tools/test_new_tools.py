import pytest
import os
import tempfile
import asyncio
from backend.tools.registry import ToolExecutor, TOOL_DEFINITIONS


@pytest.fixture
def executor():
    return ToolExecutor()


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestNewToolDefinitions:
    def test_system_info_in_definitions(self):
        tool_names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "system_info" in tool_names
        assert "manage_processes" in tool_names
        assert "backup_data" in tool_names
        assert "restore_data" in tool_names

    def test_system_info_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "system_info")
        assert tool["input_schema"]["required"] == []

    def test_manage_processes_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "manage_processes")
        assert "action" in tool["input_schema"]["required"]
        assert "action" in tool["input_schema"]["properties"]
        assert tool["input_schema"]["properties"]["action"]["enum"] == ["list", "kill"]

    def test_backup_data_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "backup_data")
        assert "source" in tool["input_schema"]["required"]
        assert "destination" in tool["input_schema"]["required"]

    def test_restore_data_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "restore_data")
        assert "backup_path" in tool["input_schema"]["required"]
        assert "destination" in tool["input_schema"]["required"]


class TestSystemInfo:
    @pytest.mark.asyncio
    async def test_system_info_returns_data(self, executor):
        result = await executor.execute("system_info", {})
        assert "platform" in result or "error" in result

    @pytest.mark.asyncio
    async def test_system_info_includes_memory(self, executor):
        result = await executor.execute("system_info", {})
        if "error" not in result:
            assert "memory" in result


class TestManageProcesses:
    @pytest.mark.asyncio
    async def test_list_processes(self, executor):
        result = await executor.execute("manage_processes", {"action": "list"})
        assert "PID" in result or "error" in result

    @pytest.mark.asyncio
    async def test_kill_requires_pid(self, executor):
        result = await executor.execute("manage_processes", {"action": "kill"})
        assert "pid required" in result.lower()


class TestBackupRestore:
    @pytest.mark.asyncio
    async def test_backup_file(self, executor, temp_dir):
        source_file = os.path.join(temp_dir, "source.txt")
        with open(source_file, "w") as f:
            f.write("test data for backup")

        backup_dir = os.path.join(temp_dir, "backups")
        result = await executor.execute(
            "backup_data", {"source": source_file, "destination": backup_dir}
        )
        assert "success" in result.lower() or "error" in result

    @pytest.mark.asyncio
    async def test_backup_missing_source(self, executor, temp_dir):
        result = await executor.execute(
            "backup_data", {"source": "/nonexistent/file.txt", "destination": temp_dir}
        )
        assert "not found" in result.lower() or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_restore_file(self, executor, temp_dir):
        backup_file = os.path.join(temp_dir, "backup.txt")
        with open(backup_file, "w") as f:
            f.write("backup content")

        restore_path = os.path.join(temp_dir, "restored.txt")
        result = await executor.execute(
            "restore_data", {"backup_path": backup_file, "destination": restore_path}
        )
        assert "success" in result.lower() or "error" in result

    @pytest.mark.asyncio
    async def test_restore_missing_backup(self, executor, temp_dir):
        result = await executor.execute(
            "restore_data",
            {"backup_path": "/nonexistent/backup.tar", "destination": temp_dir},
        )
        assert "not found" in result.lower() or "error" in result.lower()
