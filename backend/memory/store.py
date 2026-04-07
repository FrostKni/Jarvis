import aiosqlite
from datetime import datetime
from backend.config import get_settings

settings = get_settings()


class PersistentStore:
    def __init__(self):
        self._db_path = settings.sqlite_db_path

    async def init(self):
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT,
                    result TEXT,
                    tool TEXT,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT,
                    trigger_at TEXT,
                    delivered INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS people (
                    name TEXT PRIMARY KEY,
                    notes TEXT,
                    last_seen TEXT
                );
                CREATE TABLE IF NOT EXISTS calendar_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    description TEXT,
                    created_at TEXT
                );
            """)
            await db.commit()

    async def set_preference(self, key: str, value: str):
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO preferences VALUES (?, ?, ?)",
                (key, value, datetime.utcnow().isoformat()),
            )
            await db.commit()

    async def get_preference(self, key: str) -> str | None:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT value FROM preferences WHERE key=?", (key,)
            ) as cur:
                row = await cur.fetchone()
                return row[0] if row else None

    async def get_all_preferences(self) -> dict:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute("SELECT key, value FROM preferences") as cur:
                rows = await cur.fetchall()
                return {r[0]: r[1] for r in rows}

    async def log_task(self, task: str, result: str, tool: str):
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO task_history (task, result, tool, created_at) VALUES (?, ?, ?, ?)",
                (task, result, tool, datetime.utcnow().isoformat()),
            )
            await db.commit()

    async def add_reminder(self, text: str, trigger_at: str):
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO reminders (text, trigger_at) VALUES (?, ?)",
                (text, trigger_at),
            )
            await db.commit()

    async def get_pending_reminders(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT id, text FROM reminders WHERE trigger_at <= ? AND delivered=0",
                (now,),
            ) as cur:
                rows = await cur.fetchall()
                return [{"id": r[0], "text": r[1]} for r in rows]

    async def mark_reminder_delivered(self, reminder_id: int):
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE reminders SET delivered=1 WHERE id=?", (reminder_id,)
            )
            await db.commit()

    async def add_calendar_event(
        self, title: str, start_time: str, end_time: str = None, description: str = None
    ) -> int:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "INSERT INTO calendar_events (title, start_time, end_time, description, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    title,
                    start_time,
                    end_time,
                    description,
                    datetime.utcnow().isoformat(),
                ),
            )
            await db.commit()
            return cursor.lastrowid

    async def search_calendar_events(
        self, query: str = None, from_date: str = None, to_date: str = None
    ) -> list[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            sql = "SELECT id, title, start_time, end_time, description FROM calendar_events WHERE 1=1"
            params = []
            if query:
                sql += " AND (title LIKE ? OR description LIKE ?)"
                params.extend([f"%{query}%", f"%{query}%"])
            if from_date:
                sql += " AND start_time >= ?"
                params.append(from_date)
            if to_date:
                sql += " AND start_time <= ?"
                params.append(to_date)
            sql += " ORDER BY start_time"
            async with db.execute(sql, params) as cur:
                rows = await cur.fetchall()
                return [
                    {
                        "id": r[0],
                        "title": r[1],
                        "start_time": r[2],
                        "end_time": r[3],
                        "description": r[4],
                    }
                    for r in rows
                ]
