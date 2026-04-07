import asyncio
import subprocess
import json
import os
from pathlib import Path
from typing import Callable, Any
from backend.config import get_settings

settings = get_settings()

TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": "Search the web for current information, news, or facts.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "add_reminder",
        "description": "Set a reminder for a specific time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "trigger_at": {"type": "string"},
            },
            "required": ["text", "trigger_at"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file from the filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file"},
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum lines to read (default 500)",
                    "default": 500,
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file on the filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file"},
                "content": {"type": "string", "description": "Content to write"},
                "append": {
                    "type": "boolean",
                    "description": "Append to file instead of overwrite",
                    "default": False,
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "search_files",
        "description": "Search for files by name pattern in a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory to search in",
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match (e.g., '*.py')",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Search recursively",
                    "default": True,
                },
            },
            "required": ["directory", "pattern"],
        },
    },
    {
        "name": "list_directory",
        "description": "List contents of a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to directory"},
                "show_hidden": {
                    "type": "boolean",
                    "description": "Show hidden files",
                    "default": False,
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "delete_file",
        "description": "Delete a file from the filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file to delete",
                },
                "confirm": {
                    "type": "boolean",
                    "description": "Confirmation flag (must be true)",
                    "default": False,
                },
            },
            "required": ["path", "confirm"],
        },
    },
]


class ToolExecutor:
    def __init__(self, store=None):
        self._store = store
        self._handlers: dict[str, Callable] = {
            "web_search": self._web_search,
            "get_weather": self._get_weather,
            "run_code": self._run_code,
            "os_open_app": self._os_open_app,
            "take_screenshot": self._take_screenshot,
            "get_stock_price": self._get_stock_price,
            "smart_home_control": self._smart_home_control,
            "add_reminder": self._add_reminder,
            "read_file": self._read_file,
            "write_file": self._write_file,
            "search_files": self._search_files,
            "list_directory": self._list_directory,
            "delete_file": self._delete_file,
        }

    async def execute(self, tool_name: str, tool_input: dict) -> str:
        handler = self._handlers.get(tool_name)
        if not handler:
            return f"Unknown tool: {tool_name}"
        try:
            return await handler(**tool_input)
        except Exception as e:
            return f"Tool error: {e}"

    async def _web_search(self, query: str) -> str:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(
                f"https://duckduckgo.com/?q={query.replace(' ', '+')}&ia=web"
            )
            await page.wait_for_selector(".result__body", timeout=5000)
            results = await page.query_selector_all(".result__body")
            texts = []
            for r in results[:5]:
                text = await r.inner_text()
                texts.append(text.strip())
            await browser.close()
            return "\n\n".join(texts)

    async def _get_weather(self, location: str) -> str:
        import aiohttp

        url = f"https://api.openweathermap.org/data/2.5/weather?q={location}&appid={settings.openweather_api_key}&units=metric"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                data = await r.json()
                if r.status != 200:
                    return f"Weather error: {data.get('message', 'unknown')}"
                w = data["weather"][0]["description"]
                temp = data["main"]["temp"]
                feels = data["main"]["feels_like"]
                return f"{location}: {w}, {temp}°C (feels like {feels}°C)"

    async def _run_code(self, code: str) -> str:
        result = await asyncio.to_thread(
            subprocess.run,
            ["python3", "-c", code],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout or result.stderr
        return output[:2000] if output else "No output"

    async def _os_open_app(self, app_name: str) -> str:
        await asyncio.to_thread(subprocess.Popen, ["xdg-open", app_name])
        return f"Opening {app_name}"

    async def _take_screenshot(self, question: str) -> str:
        import mss, base64
        from PIL import Image
        import io

        with mss.mss() as sct:
            img = sct.grab(sct.monitors[1])
            pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            pil_img.thumbnail((1280, 720))
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=70)
            b64 = base64.b64encode(buf.getvalue()).decode()
        # Vision analysis via Claude
        from backend.brain.llm import LLMClient

        llm = LLMClient()
        response = await llm._client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": question},
                    ],
                }
            ],
        )
        return response.content[0].text

    async def _get_stock_price(self, symbol: str) -> str:
        import aiohttp

        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={settings.alpha_vantage_api_key}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                data = await r.json()
                quote = data.get("Global Quote", {})
                price = quote.get("05. price", "N/A")
                change = quote.get("10. change percent", "N/A")
                return f"{symbol}: ${price} ({change})"

    async def _smart_home_control(
        self, entity_id: str, action: str, params: dict = {}
    ) -> str:
        import aiohttp

        url = f"{settings.home_assistant_url}/api/services/{entity_id.split('.')[0]}/{action}"
        headers = {"Authorization": f"Bearer {settings.home_assistant_token}"}
        payload = {"entity_id": entity_id, **params}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as r:
                return f"Smart home: {action} on {entity_id} — status {r.status}"

    async def _add_reminder(self, text: str, trigger_at: str) -> str:
        if self._store:
            await self._store.add_reminder(text, trigger_at)
        return f"Reminder set: '{text}' at {trigger_at}"

    async def _read_file(self, path: str, max_lines: int = 500) -> str:
        def _read():
            real_path = os.path.realpath(path)
            if not os.path.exists(real_path):
                return f"Error: File not found: {path}"
            if not os.path.isfile(real_path):
                return f"Error: Not a file: {path}"
            try:
                with open(real_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= max_lines:
                            lines.append(f"... (truncated, {max_lines} lines max)")
                            break
                        lines.append(line.rstrip("\n"))
                    return "\n".join(lines) if lines else "(empty file)"
            except PermissionError:
                return f"Error: Permission denied: {path}"
            except Exception as e:
                return f"Error reading file: {e}"

        return await asyncio.to_thread(_read)

    async def _write_file(self, path: str, content: str, append: bool = False) -> str:
        def _write():
            real_path = os.path.realpath(path)
            try:
                os.makedirs(os.path.dirname(real_path), exist_ok=True)
                mode = "a" if append else "w"
                with open(real_path, mode, encoding="utf-8") as f:
                    f.write(content)
                action = "appended to" if append else "written to"
                return f"Successfully {action} {path}"
            except PermissionError:
                return f"Error: Permission denied: {path}"
            except Exception as e:
                return f"Error writing file: {e}"

        return await asyncio.to_thread(_write)

    async def _search_files(
        self, directory: str, pattern: str, recursive: bool = True
    ) -> str:
        def _search():
            real_dir = os.path.realpath(directory)
            if not os.path.exists(real_dir):
                return f"Error: Directory not found: {directory}"
            if not os.path.isdir(real_dir):
                return f"Error: Not a directory: {directory}"
            try:
                search_path = Path(real_dir)
                if recursive:
                    matches = list(search_path.rglob(pattern))
                else:
                    matches = list(search_path.glob(pattern))
                if not matches:
                    return f"No files matching '{pattern}' found in {directory}"
                results = [str(m.relative_to(real_dir)) for m in matches[:100]]
                if len(matches) > 100:
                    results.append(f"... (truncated, {len(matches)} total matches)")
                return "\n".join(results)
            except PermissionError:
                return f"Error: Permission denied: {directory}"
            except Exception as e:
                return f"Error searching files: {e}"

        return await asyncio.to_thread(_search)

    async def _list_directory(self, path: str, show_hidden: bool = False) -> str:
        def _list():
            real_path = os.path.realpath(path)
            if not os.path.exists(real_path):
                return f"Error: Directory not found: {path}"
            if not os.path.isdir(real_path):
                return f"Error: Not a directory: {path}"
            try:
                entries = []
                with os.scandir(real_path) as it:
                    for entry in sorted(it, key=lambda e: e.name.lower()):
                        if not show_hidden and entry.name.startswith("."):
                            continue
                        if entry.is_dir():
                            entries.append(f"[DIR]  {entry.name}/")
                        elif entry.is_file():
                            size = entry.stat().st_size
                            entries.append(f"[FILE] {entry.name} ({size} bytes)")
                        else:
                            entries.append(f"[???]  {entry.name}")
                if not entries:
                    return f"(empty directory: {path})"
                return "\n".join(entries)
            except PermissionError:
                return f"Error: Permission denied: {path}"
            except Exception as e:
                return f"Error listing directory: {e}"

        return await asyncio.to_thread(_list)

    async def _delete_file(self, path: str, confirm: bool = False) -> str:
        def _delete():
            if not confirm:
                return "Error: Deletion requires confirm=True"
            real_path = os.path.realpath(path)
            if not os.path.exists(real_path):
                return f"Error: File not found: {path}"
            if not os.path.isfile(real_path):
                return f"Error: Not a file: {path}"
            try:
                os.remove(real_path)
                return f"Successfully deleted: {path}"
            except PermissionError:
                return f"Error: Permission denied: {path}"
            except Exception as e:
                return f"Error deleting file: {e}"

        return await asyncio.to_thread(_delete)
