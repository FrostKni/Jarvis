import asyncio
import subprocess
import json
import os
import re
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
        "name": "navigate_url",
        "description": "Navigate to a URL and wait for page to load.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to navigate to"},
                "wait_for": {
                    "type": "string",
                    "description": "CSS selector to wait for (optional)",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "fill_form",
        "description": "Fill a form field with text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector for input field",
                },
                "value": {"type": "string", "description": "Value to fill"},
                "press_enter": {
                    "type": "boolean",
                    "description": "Press Enter after filling",
                    "default": False,
                },
            },
            "required": ["selector", "value"],
        },
    },
    {
        "name": "click_element",
        "description": "Click an element on the page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector for element",
                },
                "wait_after": {
                    "type": "integer",
                    "description": "Milliseconds to wait after click",
                    "default": 1000,
                },
            },
            "required": ["selector"],
        },
    },
    {
        "name": "scrape_page",
        "description": "Extract text or data from the current page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector (optional, defaults to body)",
                },
                "attribute": {
                    "type": "string",
                    "description": "Attribute to extract (optional, defaults to text)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "screenshot_element",
        "description": "Take a screenshot of a specific element or the page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector for element (optional, defaults to viewport)",
                },
                "full_page": {
                    "type": "boolean",
                    "description": "Capture full page",
                    "default": False,
                },
            },
            "required": [],
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
    {
        "name": "send_email",
        "description": "Send an email to a recipient.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject"},
                "body": {"type": "string", "description": "Email body text"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "read_email",
        "description": "Read recent emails from inbox.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of emails to fetch",
                    "default": 5,
                },
                "unread_only": {
                    "type": "boolean",
                    "description": "Only fetch unread emails",
                    "default": False,
                },
            },
            "required": [],
        },
    },
    {
        "name": "create_calendar_event",
        "description": "Create a calendar event.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Event title"},
                "start_time": {
                    "type": "string",
                    "description": "Start time (ISO format)",
                },
                "end_time": {"type": "string", "description": "End time (ISO format)"},
                "description": {"type": "string", "description": "Event description"},
            },
            "required": ["title", "start_time"],
        },
    },
    {
        "name": "search_calendar",
        "description": "Search for calendar events.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (title or description)",
                },
                "from_date": {
                    "type": "string",
                    "description": "Start of date range (ISO)",
                },
                "to_date": {"type": "string", "description": "End of date range (ISO)"},
            },
            "required": [],
        },
    },
    {
        "name": "execute_terminal",
        "description": "Execute a terminal command safely.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to execute"},
                "cwd": {
                    "type": "string",
                    "description": "Working directory (optional)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 30,
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "git_status",
        "description": "Check git repository status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to git repository (optional, defaults to cwd)",
                }
            },
            "required": [],
        },
    },
    {
        "name": "git_commit",
        "description": "Create a git commit.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Commit message"},
                "repo_path": {
                    "type": "string",
                    "description": "Path to git repository (optional)",
                },
                "add_all": {
                    "type": "boolean",
                    "description": "Stage all changes before commit",
                    "default": False,
                },
            },
            "required": ["message"],
        },
    },
    {
        "name": "git_push",
        "description": "Push commits to remote repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to git repository (optional)",
                },
                "remote": {
                    "type": "string",
                    "description": "Remote name",
                    "default": "origin",
                },
                "branch": {
                    "type": "string",
                    "description": "Branch name (optional, defaults to current)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "search_code",
        "description": "Search for code patterns in files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory to search in",
                },
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File glob pattern (e.g., '*.py')",
                    "default": "*",
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Lines of context",
                    "default": 2,
                },
            },
            "required": ["directory", "pattern"],
        },
    },
    {
        "name": "query_sqlite",
        "description": "Execute a SQL query on a SQLite database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "db_path": {"type": "string", "description": "Path to SQLite database"},
                "query": {"type": "string", "description": "SQL query to execute"},
                "params": {
                    "type": "array",
                    "description": "Query parameters (optional)",
                },
            },
            "required": ["db_path", "query"],
        },
    },
    {
        "name": "query_postgres",
        "description": "Execute a SQL query on a PostgreSQL database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "connection_string": {
                    "type": "string",
                    "description": "PostgreSQL connection string",
                },
                "query": {"type": "string", "description": "SQL query to execute"},
                "params": {
                    "type": "array",
                    "description": "Query parameters (optional)",
                },
            },
            "required": ["connection_string", "query"],
        },
    },
    {
        "name": "query_mongodb",
        "description": "Execute a query on a MongoDB database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "connection_string": {
                    "type": "string",
                    "description": "MongoDB connection string",
                },
                "database": {"type": "string", "description": "Database name"},
                "collection": {"type": "string", "description": "Collection name"},
                "query": {"type": "object", "description": "MongoDB query (JSON)"},
                "limit": {
                    "type": "integer",
                    "description": "Max results",
                    "default": 100,
                },
            },
            "required": ["connection_string", "database", "collection", "query"],
        },
    },
    {
        "name": "execute_code_sandbox",
        "description": "Execute code securely in a Docker sandbox. Supports Python, JavaScript, and Bash.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Code to execute"},
                "language": {
                    "type": "string",
                    "description": "Language (python, javascript, bash)",
                    "default": "python",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (max 60)",
                    "default": 30,
                },
            },
            "required": ["code"],
        },
    },
]

BLOCKED_COMMANDS = [
    "rm -rf /",
    "rm -rf ~",
    "sudo",
    "chmod 777",
    "> /dev/",
    "mkfs",
    "dd if=",
]


class ToolExecutor:
    def __init__(self, store=None):
        self._store = store
        self._playwright = None
        self._browser = None
        self._page = None
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
            "navigate_url": self._navigate_url,
            "fill_form": self._fill_form,
            "click_element": self._click_element,
            "scrape_page": self._scrape_page,
            "screenshot_element": self._screenshot_element,
            "send_email": self._send_email,
            "read_email": self._read_email,
            "create_calendar_event": self._create_calendar_event,
            "search_calendar": self._search_calendar,
            "execute_terminal": self._execute_terminal,
            "git_status": self._git_status,
            "git_commit": self._git_commit,
            "git_push": self._git_push,
            "search_code": self._search_code,
            "query_sqlite": self._query_sqlite,
            "query_postgres": self._query_postgres,
            "query_mongodb": self._query_mongodb,
            "execute_code_sandbox": self._execute_code_sandbox,
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

    async def _ensure_browser(self):
        from playwright.async_api import async_playwright

        if not self._playwright:
            self._playwright = await async_playwright().start()
        if not self._browser:
            self._browser = await self._playwright.chromium.launch(headless=True)
        if not self._page:
            self._page = await self._browser.new_page()

    async def _navigate_url(self, url: str, wait_for: str = None) -> str:
        try:
            await self._ensure_browser()
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            await self._page.goto(url, timeout=30000)
            if wait_for:
                await self._page.wait_for_selector(wait_for, timeout=5000)
            title = await self._page.title()
            return f"Navigated to {url} - Title: {title}"
        except Exception as e:
            if self._browser:
                await self._browser.close()
                self._browser = None
                self._page = None
            return f"Error navigating to {url}: {e}"

    async def _fill_form(
        self, selector: str, value: str, press_enter: bool = False
    ) -> str:
        try:
            await self._ensure_browser()
            element = await self._page.wait_for_selector(selector, timeout=5000)
            await element.fill(value)
            if press_enter:
                await element.press("Enter")
            return f"Filled '{value}' into {selector}"
        except Exception as e:
            return f"Error filling form: {e}"

    async def _click_element(self, selector: str, wait_after: int = 1000) -> str:
        try:
            await self._ensure_browser()
            element = await self._page.wait_for_selector(selector, timeout=5000)
            await element.click()
            await asyncio.sleep(wait_after / 1000)
            return f"Clicked {selector}"
        except Exception as e:
            return f"Error clicking element: {e}"

    async def _scrape_page(self, selector: str = None, attribute: str = None) -> str:
        try:
            await self._ensure_browser()
            target = selector or "body"
            element = await self._page.wait_for_selector(target, timeout=5000)
            if attribute:
                value = await element.get_attribute(attribute)
                return value or f"No attribute '{attribute}' found"
            text = await element.inner_text()
            return text.strip()
        except Exception as e:
            return f"Error scraping page: {e}"

    async def _screenshot_element(
        self, selector: str = None, full_page: bool = False
    ) -> str:
        import base64

        try:
            await self._ensure_browser()
            if selector:
                element = await self._page.wait_for_selector(selector, timeout=5000)
                screenshot_bytes = await element.screenshot()
            else:
                screenshot_bytes = await self._page.screenshot(full_page=full_page)
            b64 = base64.b64encode(screenshot_bytes).decode()
            return b64
        except Exception as e:
            return f"Error taking screenshot: {e}"

    async def _send_email(self, to: str, subject: str, body: str) -> str:
        if not settings.smtp_host or not settings.smtp_user:
            return f"[MOCK] Email would be sent to {to} with subject: {subject}"
        import smtplib
        from email.mime.text import MIMEText

        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = settings.smtp_user
            msg["To"] = to

            def _send():
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                    server.starttls()
                    server.login(settings.smtp_user, settings.smtp_password)
                    server.send_message(msg)

            await asyncio.to_thread(_send)
            return f"Email sent to {to}"
        except Exception as e:
            return f"Error sending email: {e}"

    async def _read_email(self, limit: int = 5, unread_only: bool = False) -> str:
        if not settings.smtp_host or not settings.smtp_user:
            return "[MOCK] No emails configured. Set SMTP settings to read real emails."
        import imaplib
        import email
        from email.header import decode_header

        try:

            def _read():
                emails = []
                with imaplib.IMAP4_SSL(settings.smtp_host) as mail:
                    mail.login(settings.smtp_user, settings.smtp_password)
                    mail.select("inbox")
                    status, messages = mail.search(
                        None, "ALL" if not unread_only else "UNSEEN"
                    )
                    email_ids = messages[0].split()[:limit]
                    for eid in email_ids:
                        status, msg_data = mail.fetch(eid, "(RFC822)")
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])
                                subject, _ = decode_header(msg["Subject"])[0]
                                if isinstance(subject, bytes):
                                    subject = subject.decode()
                                from_ = msg.get("From", "Unknown")
                                emails.append(f"From: {from_}\nSubject: {subject}")
                return emails

            emails = await asyncio.to_thread(_read)
            if not emails:
                return "No emails found"
            return "\n\n---\n\n".join(emails)
        except Exception as e:
            return f"Error reading emails: {e}"

    async def _create_calendar_event(
        self, title: str, start_time: str, end_time: str = None, description: str = None
    ) -> str:
        if not self._store:
            return "Error: Store not available"
        try:
            event_id = await self._store.add_calendar_event(
                title=title,
                start_time=start_time,
                end_time=end_time,
                description=description,
            )
            return f"Event created: '{title}' (ID: {event_id})"
        except Exception as e:
            return f"Error creating event: {e}"

    async def _search_calendar(
        self, query: str = None, from_date: str = None, to_date: str = None
    ) -> str:
        if not self._store:
            return "Error: Store not available"
        try:
            events = await self._store.search_calendar_events(
                query=query, from_date=from_date, to_date=to_date
            )
            if not events:
                return "No matching events found"
            lines = []
            for e in events:
                line = f"- {e['title']} at {e['start_time']}"
                if e.get("description"):
                    line += f" | {e['description']}"
                lines.append(line)
            return "\n".join(lines)
        except Exception as e:
            return f"Error searching calendar: {e}"

    async def _execute_terminal(
        self, command: str, cwd: str = None, timeout: int = 30
    ) -> str:
        for blocked in BLOCKED_COMMANDS:
            if blocked in command:
                return f"Error: Command blocked (dangerous operation): {blocked}"

        def _run():
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=cwd,
                )
                output = result.stdout + result.stderr
                if len(output) > 5000:
                    output = output[:5000] + "\n... (output truncated)"
                return output.strip() if output.strip() else "(no output)"
            except subprocess.TimeoutExpired:
                return f"Error: Command timed out after {timeout} seconds"
            except Exception as e:
                return f"Error executing command: {e}"

        return await asyncio.to_thread(_run)

    async def _git_status(self, repo_path: str = None) -> str:
        def _status():
            try:
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True,
                    text=True,
                    cwd=repo_path,
                )
                if result.returncode != 0 and "not a git repository" in result.stderr:
                    return "Error: Not a git repository"
                lines = (
                    result.stdout.strip().split("\n") if result.stdout.strip() else []
                )
                if not lines or lines == [""]:
                    return "Working tree clean"
                status_map = {
                    "M": "modified",
                    "A": "added",
                    "D": "deleted",
                    "R": "renamed",
                    "C": "copied",
                    "??": "untracked",
                }
                output = []
                for line in lines:
                    if not line:
                        continue
                    code = line[:2].strip()
                    file_path = line[3:]
                    status = status_map.get(code, code)
                    output.append(f"[{status}] {file_path}")
                return "\n".join(output)
            except Exception as e:
                return f"Error checking git status: {e}"

        return await asyncio.to_thread(_status)

    async def _git_commit(
        self, message: str, repo_path: str = None, add_all: bool = False
    ) -> str:
        def _commit():
            try:
                if add_all:
                    subprocess.run(
                        ["git", "add", "."],
                        capture_output=True,
                        cwd=repo_path,
                    )
                result = subprocess.run(
                    ["git", "commit", "-m", message],
                    capture_output=True,
                    text=True,
                    cwd=repo_path,
                )
                if result.returncode != 0:
                    if "nothing to commit" in result.stdout:
                        return "Nothing to commit, working tree clean"
                    if "no changes added to commit" in result.stdout:
                        return "No changes staged for commit. Use add_all=True to stage all changes."
                    return f"Error: {result.stderr.strip()}"
                hash_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    cwd=repo_path,
                )
                commit_hash = hash_result.stdout.strip()[:7]
                return f"Committed: {commit_hash} - {message}"
            except Exception as e:
                return f"Error creating commit: {e}"

        return await asyncio.to_thread(_commit)

    async def _git_push(
        self, repo_path: str = None, remote: str = "origin", branch: str = None
    ) -> str:
        def _push():
            try:
                cmd = ["git", "push", remote]
                if branch:
                    cmd.append(branch)
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=repo_path,
                )
                if result.returncode != 0:
                    if (
                        "no remote" in result.stderr.lower()
                        or "does not appear to be a git repository" in result.stderr
                    ):
                        return "Error: No remote repository configured"
                    return f"Error: {result.stderr.strip()}"
                return f"Pushed to {remote}" + (f"/{branch}" if branch else "")
            except Exception as e:
                return f"Error pushing to remote: {e}"

        return await asyncio.to_thread(_push)

    async def _search_code(
        self,
        directory: str,
        pattern: str,
        file_pattern: str = "*",
        context_lines: int = 2,
    ) -> str:
        def _search():
            try:
                real_dir = os.path.realpath(directory)
                if not os.path.exists(real_dir):
                    return f"Error: Directory not found: {directory}"
                if not os.path.isdir(real_dir):
                    return f"Error: Not a directory: {directory}"
                regex = re.compile(pattern, re.IGNORECASE)
                matches = []
                search_path = Path(real_dir)
                for file_path in search_path.rglob(file_pattern):
                    if not file_path.is_file():
                        continue
                    try:
                        with open(
                            file_path, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            lines = f.readlines()
                        for i, line in enumerate(lines):
                            if regex.search(line):
                                start = max(0, i - context_lines)
                                end = min(len(lines), i + context_lines + 1)
                                context = []
                                for j in range(start, end):
                                    prefix = ">>>" if j == i else "   "
                                    context.append(
                                        f"{prefix} {file_path.name}:{j + 1}: {lines[j].rstrip()}"
                                    )
                                matches.append("\n".join(context))
                    except (PermissionError, UnicodeDecodeError):
                        continue
                if not matches:
                    return "No matches found"
                result = "\n\n".join(matches[:50])
                if len(matches) > 50:
                    result += f"\n\n... ({len(matches) - 50} more matches)"
                return result
            except Exception as e:
                return f"Error searching code: {e}"

        return await asyncio.to_thread(_search)

    async def _execute_code_sandbox(
        self, code: str, language: str = "python", timeout: int = 30
    ) -> str:
        from backend.tools.sandbox import CodeSandbox

        sandbox = CodeSandbox()
        result = await sandbox.execute(code=code, language=language, timeout=timeout)

        if not result.get("success"):
            error = result.get("error", "Unknown error")
            return f"Execution failed: {error}"

        output_parts = []
        if result.get("stdout"):
            output_parts.append(result["stdout"])
        if result.get("stderr"):
            output_parts.append(f"[stderr]\n{result['stderr']}")

        output = "\n".join(output_parts).strip()
        if not output:
            output = "(no output)"

        exit_code = result.get("exit_code", 0)
        exec_time = result.get("execution_time", 0)

        return f"{output}\n\n[Exit code: {exit_code}, Time: {exec_time:.2f}s]"

    DANGEROUS_SQL = ["DROP DATABASE", "DROP SCHEMA", "TRUNCATE TABLE", "DROP TABLE"]

    def _validate_sql(self, query: str) -> bool:
        upper = query.strip().upper()
        for dangerous in self.DANGEROUS_SQL:
            if dangerous in upper:
                return False
        return True

    async def _query_sqlite(self, db_path: str, query: str, params: list = None) -> str:
        import aiosqlite

        if not self._validate_sql(query):
            return "Error: Query contains dangerous operations"

        real_path = os.path.realpath(db_path)
        if not os.path.exists(real_path):
            return f"Error: Database not found: {db_path}"

        try:
            async with aiosqlite.connect(real_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(query, params or []) as cursor:
                    if query.strip().upper().startswith("SELECT"):
                        rows = await cursor.fetchall()
                        columns = (
                            [d[0] for d in cursor.description]
                            if cursor.description
                            else []
                        )
                        return json.dumps([dict(zip(columns, row)) for row in rows])
                    else:
                        await db.commit()
                        return f"Query executed. Rows affected: {cursor.rowcount}"
        except Exception as e:
            return f"Error executing SQLite query: {e}"

    async def _query_postgres(
        self, connection_string: str, query: str, params: list = None
    ) -> str:
        import asyncpg

        if not self._validate_sql(query):
            return "Error: Query contains dangerous operations"

        conn = None
        try:
            conn = await asyncpg.connect(connection_string)
            if query.strip().upper().startswith("SELECT"):
                rows = await conn.fetch(query, *(params or []))
                return json.dumps([dict(r) for r in rows])
            else:
                result = await conn.execute(query, *(params or []))
                return f"Query executed: {result}"
        except Exception as e:
            return f"Error executing PostgreSQL query: {e}"
        finally:
            if conn:
                await conn.close()

    async def _query_mongodb(
        self,
        connection_string: str,
        database: str,
        collection: str,
        query: dict,
        limit: int = 100,
    ) -> str:
        from motor.motor_asyncio import AsyncIOMotorClient

        client = None
        try:
            client = AsyncIOMotorClient(connection_string)
            db = client[database]
            coll = db[collection]
            cursor = coll.find(query).limit(limit)
            docs = await cursor.to_list(length=limit)
            return json.dumps(docs, default=str)
        except Exception as e:
            return f"Error executing MongoDB query: {e}"
        finally:
            if client:
                client.close()
