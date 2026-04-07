import pytest
import os
import tempfile
import sqlite3
import json
from backend.tools.registry import ToolExecutor, TOOL_DEFINITIONS


@pytest.fixture
def executor():
    return ToolExecutor()


@pytest.fixture
def temp_sqlite_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
    conn.execute(
        "INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')"
    )
    conn.execute("INSERT INTO users (name, email) VALUES ('Bob', 'bob@example.com')")
    conn.commit()
    conn.close()
    yield db_path
    os.unlink(db_path)


class TestToolDefinitions:
    def test_database_tools_in_definitions(self):
        tool_names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "query_sqlite" in tool_names
        assert "query_postgres" in tool_names
        assert "query_mongodb" in tool_names

    def test_query_sqlite_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "query_sqlite")
        assert "db_path" in tool["input_schema"]["properties"]
        assert "query" in tool["input_schema"]["properties"]
        assert "params" in tool["input_schema"]["properties"]
        assert "db_path" in tool["input_schema"]["required"]
        assert "query" in tool["input_schema"]["required"]

    def test_query_postgres_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "query_postgres")
        assert "connection_string" in tool["input_schema"]["properties"]
        assert "query" in tool["input_schema"]["properties"]
        assert "params" in tool["input_schema"]["properties"]
        assert "connection_string" in tool["input_schema"]["required"]
        assert "query" in tool["input_schema"]["required"]

    def test_query_mongodb_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "query_mongodb")
        assert "connection_string" in tool["input_schema"]["properties"]
        assert "database" in tool["input_schema"]["properties"]
        assert "collection" in tool["input_schema"]["properties"]
        assert "query" in tool["input_schema"]["properties"]
        assert "limit" in tool["input_schema"]["properties"]
        assert tool["input_schema"]["properties"]["limit"]["default"] == 100


class TestQuerySQLite:
    @pytest.mark.asyncio
    async def test_select_query(self, executor, temp_sqlite_db):
        result = await executor.execute(
            "query_sqlite",
            {"db_path": temp_sqlite_db, "query": "SELECT * FROM users"},
        )
        data = json.loads(result)
        assert len(data) == 2
        assert data[0]["name"] == "Alice"
        assert data[1]["name"] == "Bob"

    @pytest.mark.asyncio
    async def test_select_with_params(self, executor, temp_sqlite_db):
        result = await executor.execute(
            "query_sqlite",
            {
                "db_path": temp_sqlite_db,
                "query": "SELECT * FROM users WHERE name = ?",
                "params": ["Alice"],
            },
        )
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_insert_query(self, executor, temp_sqlite_db):
        result = await executor.execute(
            "query_sqlite",
            {
                "db_path": temp_sqlite_db,
                "query": "INSERT INTO users (name, email) VALUES (?, ?)",
                "params": ["Charlie", "charlie@example.com"],
            },
        )
        assert "Rows affected: 1" in result

        verify = await executor.execute(
            "query_sqlite",
            {
                "db_path": temp_sqlite_db,
                "query": "SELECT * FROM users WHERE name = 'Charlie'",
            },
        )
        data = json.loads(verify)
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_nonexistent_database(self, executor):
        result = await executor.execute(
            "query_sqlite",
            {"db_path": "/nonexistent/db.sqlite", "query": "SELECT 1"},
        )
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_dangerous_query_blocked(self, executor, temp_sqlite_db):
        result = await executor.execute(
            "query_sqlite",
            {"db_path": temp_sqlite_db, "query": "DROP TABLE users"},
        )
        assert "dangerous" in result.lower()

    @pytest.mark.asyncio
    async def test_invalid_sql(self, executor, temp_sqlite_db):
        result = await executor.execute(
            "query_sqlite",
            {"db_path": temp_sqlite_db, "query": "SELECT * FROM nonexistent_table"},
        )
        assert "error" in result.lower()


class TestQueryPostgres:
    @pytest.mark.asyncio
    async def test_connection_error_handled(self, executor):
        result = await executor.execute(
            "query_postgres",
            {
                "connection_string": "postgresql://invalid:invalid@localhost:5432/invalid",
                "query": "SELECT 1",
            },
        )
        assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_dangerous_query_blocked(self, executor):
        result = await executor.execute(
            "query_postgres",
            {
                "connection_string": "postgresql://test:test@localhost/test",
                "query": "DROP DATABASE test",
            },
        )
        assert "dangerous" in result.lower()


class TestQueryMongoDB:
    @pytest.mark.asyncio
    async def test_connection_error_handled(self, executor):
        result = await executor.execute(
            "query_mongodb",
            {
                "connection_string": "mongodb://invalid:27017",
                "database": "test",
                "collection": "test",
                "query": {},
            },
        )
        assert "error" in result.lower()


class TestSQLValidation:
    def test_valid_select(self, executor):
        assert executor._validate_sql("SELECT * FROM users") is True

    def test_valid_insert(self, executor):
        assert executor._validate_sql("INSERT INTO users VALUES (1, 'test')") is True

    def test_valid_update(self, executor):
        assert executor._validate_sql("UPDATE users SET name = 'test'") is True

    def test_valid_delete(self, executor):
        assert executor._validate_sql("DELETE FROM users WHERE id = 1") is True

    def test_blocks_drop_database(self, executor):
        assert executor._validate_sql("DROP DATABASE test") is False

    def test_blocks_drop_schema(self, executor):
        assert executor._validate_sql("DROP SCHEMA public") is False

    def test_blocks_truncate(self, executor):
        assert executor._validate_sql("TRUNCATE TABLE users") is False

    def test_blocks_drop_table(self, executor):
        assert executor._validate_sql("DROP TABLE users") is False

    def test_case_insensitive(self, executor):
        assert executor._validate_sql("drop database test") is False
