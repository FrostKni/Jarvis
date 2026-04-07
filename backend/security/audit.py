import json
from datetime import datetime, timezone
from typing import Optional
from backend.memory.store import PersistentStore


class AuditLogger:
    """Log security-relevant events."""

    def __init__(self, store: PersistentStore):
        self.store = store
        self._events_table_created = False

    async def _ensure_table(self):
        if self._events_table_created:
            return
        import aiosqlite

        async with aiosqlite.connect(self.store._db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    details TEXT,
                    severity TEXT DEFAULT 'info',
                    created_at TEXT
                )
            """)
            await db.commit()
        self._events_table_created = True

    async def log_event(self, event_type: str, details: dict, severity: str = "info"):
        """Log a security event."""
        await self._ensure_table()
        import aiosqlite

        async with aiosqlite.connect(self.store._db_path) as db:
            await db.execute(
                """INSERT INTO audit_events 
                   (event_type, details, severity, created_at) 
                   VALUES (?, ?, ?, ?)""",
                (
                    event_type,
                    json.dumps(details),
                    severity,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            await db.commit()

    async def get_events(self, limit: int = 100, event_type: str = None) -> list:
        """Get recent audit events."""
        await self._ensure_table()
        import aiosqlite

        async with aiosqlite.connect(self.store._db_path) as db:
            if event_type:
                async with db.execute(
                    """SELECT id, event_type, details, severity, created_at 
                       FROM audit_events 
                       WHERE event_type = ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (event_type, limit),
                ) as cur:
                    rows = await cur.fetchall()
            else:
                async with db.execute(
                    """SELECT id, event_type, details, severity, created_at 
                       FROM audit_events 
                       ORDER BY created_at DESC LIMIT ?""",
                    (limit,),
                ) as cur:
                    rows = await cur.fetchall()

            return [
                {
                    "id": r[0],
                    "event_type": r[1],
                    "details": json.loads(r[2]) if r[2] else {},
                    "severity": r[3],
                    "created_at": r[4],
                }
                for r in rows
            ]

    async def log_tool_execution(
        self, tool_name: str, params: dict, result: str, success: bool = True
    ):
        """Log a tool execution event."""
        await self.log_event(
            event_type="tool_execution",
            details={
                "tool": tool_name,
                "params": params,
                "result_preview": result[:500] if result else None,
                "success": success,
            },
            severity="info" if success else "warning",
        )

    async def log_authentication(
        self, user_id: str, action: str, success: bool = True, ip_address: str = None
    ):
        """Log authentication events."""
        await self.log_event(
            event_type="authentication",
            details={
                "user_id": user_id,
                "action": action,
                "success": success,
                "ip_address": ip_address,
            },
            severity="info" if success else "warning",
        )

    async def log_data_access(self, resource: str, action: str, user_id: str = None):
        """Log data access events."""
        await self.log_event(
            event_type="data_access",
            details={
                "resource": resource,
                "action": action,
                "user_id": user_id,
            },
            severity="info",
        )
