import asyncio
import subprocess
import json
from typing import Callable, Any
from backend.config import get_settings

settings = get_settings()

TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": "Search the web for current information, news, or facts.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "get_weather",
        "description": "Get current weather for a location.",
        "input_schema": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]},
    },
    {
        "name": "run_code",
        "description": "Execute Python code in a sandbox and return output.",
        "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
    },
    {
        "name": "os_open_app",
        "description": "Open an application by name on the user's computer.",
        "input_schema": {"type": "object", "properties": {"app_name": {"type": "string"}}, "required": ["app_name"]},
    },
    {
        "name": "take_screenshot",
        "description": "Take a screenshot of the current screen and analyze it.",
        "input_schema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
    },
    {
        "name": "get_stock_price",
        "description": "Get current stock or crypto price.",
        "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]},
    },
    {
        "name": "smart_home_control",
        "description": "Control smart home devices via Home Assistant.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "action": {"type": "string"},
                "params": {"type": "object"},
            },
            "required": ["entity_id", "action"],
        },
    },
    {
        "name": "add_reminder",
        "description": "Set a reminder for a specific time.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}, "trigger_at": {"type": "string"}},
            "required": ["text", "trigger_at"],
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
            await page.goto(f"https://duckduckgo.com/?q={query.replace(' ', '+')}&ia=web")
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
            capture_output=True, text=True, timeout=10,
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
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": question},
                ],
            }],
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

    async def _smart_home_control(self, entity_id: str, action: str, params: dict = {}) -> str:
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
