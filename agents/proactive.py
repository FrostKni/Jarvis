import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.memory.store import PersistentStore
from backend.memory.session import SessionCache
from backend.config import get_settings
import aiohttp

settings = get_settings()


class ProactiveAgent:
    def __init__(self, store: PersistentStore, session: SessionCache, on_alert: callable):
        self._store = store
        self._session = session
        self._on_alert = on_alert  # async callable(text: str)
        self._scheduler = AsyncIOScheduler()

    def start(self):
        self._scheduler.add_job(self._check_reminders, "interval", seconds=30)
        self._scheduler.add_job(self._check_weather, "interval", minutes=60)
        self._scheduler.add_job(self._check_system_health, "interval", minutes=5)
        self._scheduler.start()

    def stop(self):
        self._scheduler.shutdown(wait=False)

    async def _check_reminders(self):
        reminders = await self._store.get_pending_reminders()
        for r in reminders:
            await self._on_alert(f"Reminder: {r['text']}")
            await self._store.mark_reminder_delivered(r["id"])

    async def _check_weather(self):
        location = await self._store.get_preference("location")
        if not location or not settings.openweather_api_key:
            return
        url = f"https://api.openweathermap.org/data/2.5/weather?q={location}&appid={settings.openweather_api_key}&units=metric"
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                if r.status == 200:
                    data = await r.json()
                    condition = data["weather"][0]["main"]
                    if condition in ("Rain", "Thunderstorm", "Snow"):
                        await self._on_alert(f"Heads up — {condition} expected in {location}.")

    async def _check_system_health(self):
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory().percent
        if cpu > 90:
            await self._on_alert(f"CPU usage is at {cpu:.0f}%. You may want to check running processes.")
        if mem > 90:
            await self._on_alert(f"Memory usage is at {mem:.0f}%. Consider closing some applications.")
