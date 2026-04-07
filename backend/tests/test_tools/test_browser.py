import pytest
import os
import subprocess
from backend.tools.registry import ToolExecutor, TOOL_DEFINITIONS


def playwright_working():
    try:
        from playwright.async_api import async_playwright
        import asyncio

        async def test_connection():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await browser.close()
                return True

        return asyncio.get_event_loop().run_until_complete(test_connection())
    except Exception:
        return False


PLAYWRIGHT_WORKS = playwright_working()


@pytest.fixture
def executor():
    return ToolExecutor()


class TestBrowserToolDefinitions:
    def test_browser_tools_in_definitions(self):
        tool_names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "navigate_url" in tool_names
        assert "fill_form" in tool_names
        assert "click_element" in tool_names
        assert "scrape_page" in tool_names
        assert "screenshot_element" in tool_names

    def test_navigate_url_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "navigate_url")
        assert "url" in tool["input_schema"]["properties"]
        assert "wait_for" in tool["input_schema"]["properties"]
        assert tool["input_schema"]["required"] == ["url"]

    def test_fill_form_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "fill_form")
        props = tool["input_schema"]["properties"]
        assert "selector" in props
        assert "value" in props
        assert "press_enter" in props
        assert tool["input_schema"]["required"] == ["selector", "value"]

    def test_click_element_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "click_element")
        props = tool["input_schema"]["properties"]
        assert "selector" in props
        assert "wait_after" in props
        assert tool["input_schema"]["required"] == ["selector"]

    def test_scrape_page_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "scrape_page")
        props = tool["input_schema"]["properties"]
        assert "selector" in props
        assert "attribute" in props
        assert tool["input_schema"]["required"] == []

    def test_screenshot_element_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "screenshot_element")
        props = tool["input_schema"]["properties"]
        assert "selector" in props
        assert "full_page" in props
        assert tool["input_schema"]["required"] == []


@pytest.mark.skipif(
    not PLAYWRIGHT_WORKS, reason="Playwright browser driver not working"
)
class TestNavigateUrl:
    @pytest.mark.asyncio
    async def test_navigate_to_url(self, executor):
        result = await executor.execute("navigate_url", {"url": "https://example.com"})
        assert "example" in result.lower() or "success" in result.lower()

    @pytest.mark.asyncio
    async def test_navigate_with_wait_selector(self, executor):
        result = await executor.execute(
            "navigate_url",
            {"url": "https://example.com", "wait_for": "body"},
        )
        assert result and "error" not in result.lower()

    @pytest.mark.asyncio
    async def test_navigate_invalid_url(self, executor):
        result = await executor.execute("navigate_url", {"url": "not-a-valid-url"})
        assert "error" in result.lower() or "invalid" in result.lower()


@pytest.mark.skipif(
    not PLAYWRIGHT_WORKS, reason="Playwright browser driver not working"
)
class TestScrapePage:
    @pytest.mark.asyncio
    async def test_scrape_entire_page(self, executor):
        await executor.execute("navigate_url", {"url": "https://example.com"})
        result = await executor.execute("scrape_page", {})
        assert result and len(result) > 0

    @pytest.mark.asyncio
    async def test_scrape_with_selector(self, executor):
        await executor.execute("navigate_url", {"url": "https://example.com"})
        result = await executor.execute("scrape_page", {"selector": "h1"})
        assert result and len(result) > 0


@pytest.mark.skipif(
    not PLAYWRIGHT_WORKS, reason="Playwright browser driver not working"
)
class TestFillForm:
    @pytest.mark.asyncio
    async def test_fill_input_field(self, executor):
        await executor.execute(
            "navigate_url", {"url": "https://www.google.com", "wait_for": "input"}
        )
        result = await executor.execute(
            "fill_form",
            {"selector": "input[name='q']", "value": "test query"},
        )
        assert result and "error" not in result.lower()


@pytest.mark.skipif(
    not PLAYWRIGHT_WORKS, reason="Playwright browser driver not working"
)
class TestClickElement:
    @pytest.mark.asyncio
    async def test_click_button(self, executor):
        await executor.execute("navigate_url", {"url": "https://example.com"})
        result = await executor.execute(
            "click_element", {"selector": "a", "wait_after": 500}
        )
        assert result is not None


@pytest.mark.skipif(
    not PLAYWRIGHT_WORKS, reason="Playwright browser driver not working"
)
class TestScreenshotElement:
    @pytest.mark.asyncio
    async def test_screenshot_full_page(self, executor):
        await executor.execute("navigate_url", {"url": "https://example.com"})
        result = await executor.execute("screenshot_element", {"full_page": True})
        assert result and len(result) > 100

    @pytest.mark.asyncio
    async def test_screenshot_element_by_selector(self, executor):
        await executor.execute("navigate_url", {"url": "https://example.com"})
        result = await executor.execute("screenshot_element", {"selector": "h1"})
        assert result and len(result) > 50
