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


class TestToolDefinitions:
    def test_file_tools_in_definitions(self):
        tool_names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "search_files" in tool_names
        assert "list_directory" in tool_names
        assert "delete_file" in tool_names

    def test_read_file_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "read_file")
        assert "path" in tool["input_schema"]["properties"]
        assert "max_lines" in tool["input_schema"]["properties"]
        assert tool["input_schema"]["properties"]["max_lines"]["default"] == 500

    def test_write_file_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "write_file")
        assert "path" in tool["input_schema"]["properties"]
        assert "content" in tool["input_schema"]["properties"]
        assert "append" in tool["input_schema"]["properties"]
        assert tool["input_schema"]["properties"]["append"]["default"] == False

    def test_delete_file_requires_confirm(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "delete_file")
        assert "confirm" in tool["input_schema"]["required"]


class TestReadFile:
    @pytest.mark.asyncio
    async def test_read_existing_file(self, executor, temp_dir):
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("line1\nline2\nline3")

        result = await executor.execute("read_file", {"path": test_file})
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, executor):
        result = await executor.execute("read_file", {"path": "/nonexistent/file.txt"})
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_read_with_max_lines(self, executor, temp_dir):
        test_file = os.path.join(temp_dir, "large.txt")
        with open(test_file, "w") as f:
            for i in range(100):
                f.write(f"line{i}\n")

        result = await executor.execute(
            "read_file", {"path": test_file, "max_lines": 10}
        )
        assert "truncated" in result.lower()


class TestWriteFile:
    @pytest.mark.asyncio
    async def test_write_new_file(self, executor, temp_dir):
        test_file = os.path.join(temp_dir, "new.txt")
        result = await executor.execute(
            "write_file", {"path": test_file, "content": "hello world"}
        )

        assert "successfully" in result.lower()
        assert os.path.exists(test_file)
        with open(test_file) as f:
            assert f.read() == "hello world"

    @pytest.mark.asyncio
    async def test_write_creates_directories(self, executor, temp_dir):
        test_file = os.path.join(temp_dir, "subdir", "deep", "file.txt")
        result = await executor.execute(
            "write_file", {"path": test_file, "content": "test"}
        )

        assert "successfully" in result.lower()
        assert os.path.exists(test_file)

    @pytest.mark.asyncio
    async def test_append_to_file(self, executor, temp_dir):
        test_file = os.path.join(temp_dir, "append.txt")
        await executor.execute("write_file", {"path": test_file, "content": "first"})
        result = await executor.execute(
            "write_file", {"path": test_file, "content": "second", "append": True}
        )

        assert "appended" in result.lower()
        with open(test_file) as f:
            assert f.read() == "firstsecond"


class TestSearchFiles:
    @pytest.mark.asyncio
    async def test_search_finds_matches(self, executor, temp_dir):
        for name in ["test1.py", "test2.py", "other.txt"]:
            open(os.path.join(temp_dir, name), "w").close()

        result = await executor.execute(
            "search_files", {"directory": temp_dir, "pattern": "*.py"}
        )

        assert "test1.py" in result
        assert "test2.py" in result
        assert "other.txt" not in result

    @pytest.mark.asyncio
    async def test_search_recursive(self, executor, temp_dir):
        subdir = os.path.join(temp_dir, "sub")
        os.makedirs(subdir)
        open(os.path.join(subdir, "nested.py"), "w").close()

        result = await executor.execute(
            "search_files",
            {"directory": temp_dir, "pattern": "*.py", "recursive": True},
        )

        assert "nested.py" in result

    @pytest.mark.asyncio
    async def test_search_no_matches(self, executor, temp_dir):
        result = await executor.execute(
            "search_files", {"directory": temp_dir, "pattern": "*.nonexistent"}
        )
        assert "no files" in result.lower()


class TestListDirectory:
    @pytest.mark.asyncio
    async def test_list_directory_contents(self, executor, temp_dir):
        os.makedirs(os.path.join(temp_dir, "subdir"))
        open(os.path.join(temp_dir, "file.txt"), "w").close()

        result = await executor.execute("list_directory", {"path": temp_dir})

        assert "[DIR]" in result
        assert "subdir" in result
        assert "[FILE]" in result
        assert "file.txt" in result

    @pytest.mark.asyncio
    async def test_list_hidden_files(self, executor, temp_dir):
        open(os.path.join(temp_dir, ".hidden"), "w").close()
        open(os.path.join(temp_dir, "visible"), "w").close()

        result_hidden = await executor.execute(
            "list_directory", {"path": temp_dir, "show_hidden": True}
        )
        result_no_hidden = await executor.execute(
            "list_directory", {"path": temp_dir, "show_hidden": False}
        )

        assert ".hidden" in result_hidden
        assert ".hidden" not in result_no_hidden
        assert "visible" in result_hidden
        assert "visible" in result_no_hidden

    @pytest.mark.asyncio
    async def test_list_nonexistent_directory(self, executor):
        result = await executor.execute("list_directory", {"path": "/nonexistent/dir"})
        assert "not found" in result.lower()


class TestDeleteFile:
    @pytest.mark.asyncio
    async def test_delete_requires_confirm(self, executor, temp_dir):
        test_file = os.path.join(temp_dir, "todelete.txt")
        open(test_file, "w").close()

        result = await executor.execute(
            "delete_file", {"path": test_file, "confirm": False}
        )

        assert "requires confirm" in result.lower()
        assert os.path.exists(test_file)

    @pytest.mark.asyncio
    async def test_delete_with_confirm(self, executor, temp_dir):
        test_file = os.path.join(temp_dir, "delete.txt")
        open(test_file, "w").close()

        result = await executor.execute(
            "delete_file", {"path": test_file, "confirm": True}
        )

        assert "successfully deleted" in result.lower()
        assert not os.path.exists(test_file)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_file(self, executor):
        result = await executor.execute(
            "delete_file", {"path": "/nonexistent/file.txt", "confirm": True}
        )
        assert "not found" in result.lower()
