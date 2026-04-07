import pytest
import pytest_asyncio
import os
import tempfile
import asyncio
import aiosqlite
from datetime import datetime, timedelta
from backend.tools.registry import ToolExecutor, TOOL_DEFINITIONS
from backend.memory.store import PersistentStore


@pytest_asyncio.fixture
async def store():
    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "test.db")
        s = PersistentStore()
        s._db_path = db_path
        await s.init()
        yield s


@pytest.fixture
def executor(store):
    return ToolExecutor(store=store)


class TestToolDefinitions:
    def test_communication_tools_in_definitions(self):
        tool_names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "send_email" in tool_names
        assert "read_email" in tool_names
        assert "create_calendar_event" in tool_names
        assert "search_calendar" in tool_names

    def test_send_email_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "send_email")
        props = tool["input_schema"]["properties"]
        assert "to" in props
        assert "subject" in props
        assert "body" in props
        assert set(tool["input_schema"]["required"]) == {"to", "subject", "body"}

    def test_read_email_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "read_email")
        props = tool["input_schema"]["properties"]
        assert "limit" in props
        assert "unread_only" in props
        assert props["limit"]["default"] == 5
        assert props["unread_only"]["default"] == False

    def test_create_calendar_event_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "create_calendar_event")
        props = tool["input_schema"]["properties"]
        assert "title" in props
        assert "start_time" in props
        assert "end_time" in props
        assert "description" in props
        assert "title" in tool["input_schema"]["required"]
        assert "start_time" in tool["input_schema"]["required"]

    def test_search_calendar_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "search_calendar")
        props = tool["input_schema"]["properties"]
        assert "query" in props
        assert "from_date" in props
        assert "to_date" in props


class TestSendEmail:
    @pytest.mark.asyncio
    async def test_send_email_mock_mode(self, executor):
        result = await executor.execute(
            "send_email",
            {
                "to": "test@example.com",
                "subject": "Test Subject",
                "body": "Test body content",
            },
        )
        assert "sent" in result.lower() or "mock" in result.lower()

    @pytest.mark.asyncio
    async def test_send_email_validates_recipient(self, executor):
        result = await executor.execute(
            "send_email",
            {"to": "valid@email.com", "subject": "Test", "body": "Body"},
        )
        assert "valid@email.com" in result or "sent" in result.lower()


class TestReadEmail:
    @pytest.mark.asyncio
    async def test_read_email_returns_list(self, executor):
        result = await executor.execute("read_email", {"limit": 5})
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_read_email_mock_mode(self, executor):
        result = await executor.execute("read_email", {})
        assert (
            "email" in result.lower()
            or "mock" in result.lower()
            or "no email" in result.lower()
        )


class TestCreateCalendarEvent:
    @pytest.mark.asyncio
    async def test_create_event_basic(self, executor, store):
        start = datetime.utcnow().isoformat()
        end = (datetime.utcnow() + timedelta(hours=1)).isoformat()

        result = await executor.execute(
            "create_calendar_event",
            {
                "title": "Test Meeting",
                "start_time": start,
                "end_time": end,
                "description": "A test event",
            },
        )

        assert "created" in result.lower() or "event" in result.lower()

    @pytest.mark.asyncio
    async def test_create_event_minimal(self, executor):
        start = datetime.utcnow().isoformat()
        result = await executor.execute(
            "create_calendar_event", {"title": "Quick Event", "start_time": start}
        )
        assert "created" in result.lower() or "event" in result.lower()

    @pytest.mark.asyncio
    async def test_event_stored_in_database(self, executor, store):
        start = datetime.utcnow().isoformat()
        await executor.execute(
            "create_calendar_event",
            {"title": "DB Test Event", "start_time": start, "description": "Testing"},
        )

        async with aiosqlite.connect(store._db_path) as db:
            async with db.execute(
                "SELECT title, description FROM calendar_events"
            ) as cur:
                row = await cur.fetchone()
                assert row is not None
                assert row[0] == "DB Test Event"
                assert row[1] == "Testing"


class TestSearchCalendar:
    @pytest.mark.asyncio
    async def test_search_empty_calendar(self, executor):
        result = await executor.execute("search_calendar", {"query": "meeting"})
        assert (
            "no events" in result.lower()
            or "no matching" in result.lower()
            or result == ""
        )

    @pytest.mark.asyncio
    async def test_search_by_title(self, executor):
        start = datetime.utcnow().isoformat()
        await executor.execute(
            "create_calendar_event",
            {"title": "Team Standup", "start_time": start},
        )

        result = await executor.execute("search_calendar", {"query": "standup"})
        assert "standup" in result.lower()

    @pytest.mark.asyncio
    async def test_search_by_date_range(self, executor):
        now = datetime.utcnow()
        start = now.isoformat()
        end = (now + timedelta(hours=1)).isoformat()

        await executor.execute(
            "create_calendar_event",
            {"title": "Future Event", "start_time": start, "end_time": end},
        )

        from_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        to_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")

        result = await executor.execute(
            "search_calendar",
            {"from_date": from_date, "to_date": to_date},
        )
        assert "future event" in result.lower()

    @pytest.mark.asyncio
    async def test_search_returns_multiple_events(self, executor):
        now = datetime.utcnow()

        for i in range(3):
            start = (now + timedelta(hours=i)).isoformat()
            await executor.execute(
                "create_calendar_event",
                {"title": f"Meeting {i}", "start_time": start},
            )

        result = await executor.execute("search_calendar", {"query": "meeting"})
        assert "meeting 0" in result.lower()
        assert "meeting 1" in result.lower()
        assert "meeting 2" in result.lower()
