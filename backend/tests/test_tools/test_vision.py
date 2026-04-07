import pytest
import os
import tempfile
from backend.tools.registry import ToolExecutor, TOOL_DEFINITIONS


@pytest.fixture
def executor():
    return ToolExecutor()


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestToolDefinitions:
    def test_vision_tools_in_definitions(self):
        tool_names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "extract_text_from_image" in tool_names
        assert "analyze_screen_content" in tool_names
        assert "analyze_camera_frame" in tool_names
        assert "extract_pdf_text" in tool_names

    def test_extract_text_from_image_schema(self):
        tool = next(
            t for t in TOOL_DEFINITIONS if t["name"] == "extract_text_from_image"
        )
        assert "image_path" in tool["input_schema"]["properties"]
        assert "language" in tool["input_schema"]["properties"]
        assert tool["input_schema"]["properties"]["language"]["default"] == "eng"
        assert "image_path" in tool["input_schema"]["required"]

    def test_analyze_screen_content_schema(self):
        tool = next(
            t for t in TOOL_DEFINITIONS if t["name"] == "analyze_screen_content"
        )
        assert "question" in tool["input_schema"]["properties"]
        assert "region" in tool["input_schema"]["properties"]
        assert tool["input_schema"]["properties"]["region"]["default"] == "full"
        assert "question" in tool["input_schema"]["required"]

    def test_analyze_camera_frame_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "analyze_camera_frame")
        assert "question" in tool["input_schema"]["properties"]
        assert "camera_index" in tool["input_schema"]["properties"]
        assert tool["input_schema"]["properties"]["camera_index"]["default"] == 0
        assert "question" in tool["input_schema"]["required"]

    def test_extract_pdf_text_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "extract_pdf_text")
        assert "pdf_path" in tool["input_schema"]["properties"]
        assert "pages" in tool["input_schema"]["properties"]
        assert "include_metadata" in tool["input_schema"]["properties"]
        assert tool["input_schema"]["properties"]["pages"]["default"] == "all"
        assert (
            tool["input_schema"]["properties"]["include_metadata"]["default"] == False
        )
        assert "pdf_path" in tool["input_schema"]["required"]


class TestExtractTextFromImage:
    @pytest.mark.asyncio
    async def test_missing_image(self, executor):
        result = await executor.execute(
            "extract_text_from_image", {"image_path": "/nonexistent/image.png"}
        )
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_not_a_file(self, executor, temp_dir):
        result = await executor.execute(
            "extract_text_from_image", {"image_path": temp_dir}
        )
        assert "not a file" in result.lower()

    @pytest.mark.asyncio
    async def test_invalid_image(self, executor, temp_dir):
        invalid_file = os.path.join(temp_dir, "invalid.png")
        with open(invalid_file, "w") as f:
            f.write("not an image")

        result = await executor.execute(
            "extract_text_from_image", {"image_path": invalid_file}
        )
        assert "error" in result.lower() or "no text" in result.lower()


class TestExtractPdfText:
    @pytest.mark.asyncio
    async def test_missing_pdf(self, executor):
        result = await executor.execute(
            "extract_pdf_text", {"pdf_path": "/nonexistent/doc.pdf"}
        )
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_not_a_file(self, executor, temp_dir):
        result = await executor.execute("extract_pdf_text", {"pdf_path": temp_dir})
        assert "not a file" in result.lower()

    @pytest.mark.asyncio
    async def test_invalid_pdf(self, executor, temp_dir):
        invalid_pdf = os.path.join(temp_dir, "invalid.pdf")
        with open(invalid_pdf, "w") as f:
            f.write("not a pdf")

        result = await executor.execute("extract_pdf_text", {"pdf_path": invalid_pdf})
        assert "error" in result.lower()


class TestPageRangeParser:
    def test_parse_all_pages(self, executor):
        result = executor._parse_page_range("all", 10)
        assert result == list(range(10))

    def test_parse_single_page(self, executor):
        result = executor._parse_page_range("3", 10)
        assert result == [2]

    def test_parse_page_range(self, executor):
        result = executor._parse_page_range("2-5", 10)
        assert result == [1, 2, 3, 4]

    def test_parse_multiple_ranges(self, executor):
        result = executor._parse_page_range("1,3,5-7", 10)
        assert result == [0, 2, 4, 5, 6]

    def test_parse_out_of_bounds(self, executor):
        result = executor._parse_page_range("8-15", 10)
        assert result == [7, 8, 9]

    def test_parse_negative_handled(self, executor):
        result = executor._parse_page_range("0-3", 10)
        assert result == [0, 1, 2]


class TestAnalyzeScreenContent:
    @pytest.mark.asyncio
    async def test_missing_question(self, executor):
        result = await executor.execute("analyze_screen_content", {})
        assert (
            "error" in result.lower()
            or "required" in result.lower()
            or "unknown" in result.lower()
        )


class TestAnalyzeCameraFrame:
    @pytest.mark.asyncio
    async def test_missing_question(self, executor):
        result = await executor.execute("analyze_camera_frame", {})
        assert (
            "error" in result.lower()
            or "required" in result.lower()
            or "unknown" in result.lower()
        )

    @pytest.mark.asyncio
    async def test_invalid_camera_index(self, executor):
        result = await executor.execute(
            "analyze_camera_frame", {"question": "what do you see?", "camera_index": 99}
        )
        assert "error" in result.lower() or "failed" in result.lower()
