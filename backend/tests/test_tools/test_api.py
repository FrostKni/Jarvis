import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from backend.tools.registry import ToolExecutor, TOOL_DEFINITIONS


@pytest.fixture
def executor():
    return ToolExecutor(store=None)


class TestToolDefinitions:
    def test_api_tools_in_definitions(self):
        tool_names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "http_request" in tool_names
        assert "validate_response" in tool_names

    def test_http_request_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "http_request")
        props = tool["input_schema"]["properties"]
        assert "url" in props
        assert "method" in props
        assert "headers" in props
        assert "body" in props
        assert "timeout" in props
        assert "follow_redirects" in props
        assert props["method"]["default"] == "GET"
        assert props["timeout"]["default"] == 30
        assert props["follow_redirects"]["default"] == True
        assert set(tool["input_schema"]["required"]) == {"url"}

    def test_validate_response_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "validate_response")
        props = tool["input_schema"]["properties"]
        assert "response" in props
        assert "expected_status" in props
        assert "expected_headers" in props
        assert "expected_schema" in props
        assert "required_fields" in props
        assert set(tool["input_schema"]["required"]) == {"response"}


class TestHttpRequest:
    @pytest.mark.asyncio
    async def test_http_get_request(self, executor):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value={"key": "value"})
        mock_response.url = "https://api.example.com/test"
        mock_response.text = AsyncMock(return_value="")

        mock_session = AsyncMock()
        mock_session.request = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        with patch(
            "aiohttp.ClientSession",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_session)),
        ):
            result = await executor.execute(
                "http_request", {"url": "https://api.example.com/test"}
            )
            data = json.loads(result)
            assert data["status"] == 200
            assert data["body"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_http_post_request(self, executor):
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value={"created": True})
        mock_response.url = "https://api.example.com/create"
        mock_response.text = AsyncMock(return_value="")

        mock_session = AsyncMock()
        mock_session.request = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        with patch(
            "aiohttp.ClientSession",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_session)),
        ):
            result = await executor.execute(
                "http_request",
                {
                    "url": "https://api.example.com/create",
                    "method": "POST",
                    "body": {"name": "test"},
                },
            )
            data = json.loads(result)
            assert data["status"] == 201

    @pytest.mark.asyncio
    async def test_http_request_with_headers(self, executor):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value={"success": True})
        mock_response.url = "https://api.example.com/auth"
        mock_response.text = AsyncMock(return_value="")

        mock_session = AsyncMock()
        mock_session.request = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        with patch(
            "aiohttp.ClientSession",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_session)),
        ):
            result = await executor.execute(
                "http_request",
                {
                    "url": "https://api.example.com/auth",
                    "headers": {"Authorization": "Bearer token123"},
                },
            )
            data = json.loads(result)
            assert data["status"] == 200

    @pytest.mark.asyncio
    async def test_http_request_timeout(self, executor):
        mock_session = AsyncMock()
        mock_session.request = MagicMock(side_effect=asyncio.TimeoutError())

        with patch(
            "aiohttp.ClientSession",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_session)),
        ):
            result = await executor.execute(
                "http_request", {"url": "https://api.example.com/slow", "timeout": 1}
            )
            data = json.loads(result)
            assert data["status"] == 0
            assert "timed out" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_http_request_error(self, executor):
        mock_session = AsyncMock()
        mock_session.request = MagicMock(side_effect=Exception("Connection failed"))

        with patch(
            "aiohttp.ClientSession",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_session)),
        ):
            result = await executor.execute(
                "http_request", {"url": "https://api.example.com/error"}
            )
            data = json.loads(result)
            assert data["status"] == 0
            assert "Connection failed" in data["error"]

    @pytest.mark.asyncio
    async def test_http_request_text_response(self, executor):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.json = AsyncMock(side_effect=Exception("Not JSON"))
        mock_response.text = AsyncMock(return_value="Plain text response")
        mock_response.url = "https://api.example.com/text"

        mock_session = AsyncMock()
        mock_session.request = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        with patch(
            "aiohttp.ClientSession",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_session)),
        ):
            result = await executor.execute(
                "http_request", {"url": "https://api.example.com/text"}
            )
            data = json.loads(result)
            assert data["body"] == "Plain text response"


class TestValidateResponse:
    @pytest.mark.asyncio
    async def test_validate_status_code_success(self, executor):
        response = {"status": 200, "headers": {}, "body": {}}
        result = await executor.execute(
            "validate_response", {"response": response, "expected_status": 200}
        )
        data = json.loads(result)
        assert data["valid"] == True
        assert len(data["errors"]) == 0

    @pytest.mark.asyncio
    async def test_validate_status_code_failure(self, executor):
        response = {"status": 404, "headers": {}, "body": {}}
        result = await executor.execute(
            "validate_response", {"response": response, "expected_status": 200}
        )
        data = json.loads(result)
        assert data["valid"] == False
        assert any("Status code mismatch" in e for e in data["errors"])

    @pytest.mark.asyncio
    async def test_validate_headers_success(self, executor):
        response = {
            "status": 200,
            "headers": {"Content-Type": "application/json"},
            "body": {},
        }
        result = await executor.execute(
            "validate_response",
            {
                "response": response,
                "expected_headers": {"Content-Type": "application/json"},
            },
        )
        data = json.loads(result)
        assert data["valid"] == True

    @pytest.mark.asyncio
    async def test_validate_headers_failure(self, executor):
        response = {"status": 200, "headers": {"Content-Type": "text/html"}, "body": {}}
        result = await executor.execute(
            "validate_response",
            {
                "response": response,
                "expected_headers": {"Content-Type": "application/json"},
            },
        )
        data = json.loads(result)
        assert data["valid"] == False
        assert any("Header mismatch" in e for e in data["errors"])

    @pytest.mark.asyncio
    async def test_validate_required_fields_success(self, executor):
        response = {
            "status": 200,
            "headers": {},
            "body": {"id": 1, "name": "test", "email": "test@example.com"},
        }
        result = await executor.execute(
            "validate_response",
            {"response": response, "required_fields": ["id", "name", "email"]},
        )
        data = json.loads(result)
        assert data["valid"] == True

    @pytest.mark.asyncio
    async def test_validate_required_fields_failure(self, executor):
        response = {"status": 200, "headers": {}, "body": {"id": 1, "name": "test"}}
        result = await executor.execute(
            "validate_response",
            {"response": response, "required_fields": ["id", "name", "email"]},
        )
        data = json.loads(result)
        assert data["valid"] == False
        assert any("Missing required field: email" in e for e in data["errors"])

    @pytest.mark.asyncio
    async def test_validate_json_schema_success(self, executor):
        response = {"status": 200, "headers": {}, "body": {"name": "John", "age": 30}}
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name", "age"],
        }
        result = await executor.execute(
            "validate_response", {"response": response, "expected_schema": schema}
        )
        data = json.loads(result)
        assert data["valid"] == True

    @pytest.mark.asyncio
    async def test_validate_json_schema_failure(self, executor):
        response = {
            "status": 200,
            "headers": {},
            "body": {"name": "John", "age": "thirty"},
        }
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name", "age"],
        }
        result = await executor.execute(
            "validate_response", {"response": response, "expected_schema": schema}
        )
        data = json.loads(result)
        assert data["valid"] == False
        assert any("Schema validation error" in e for e in data["errors"])

    @pytest.mark.asyncio
    async def test_validate_multiple_errors(self, executor):
        response = {
            "status": 500,
            "headers": {"Content-Type": "text/html"},
            "body": {"name": "test"},
        }
        result = await executor.execute(
            "validate_response",
            {
                "response": response,
                "expected_status": 200,
                "expected_headers": {"Content-Type": "application/json"},
                "required_fields": ["name", "id"],
            },
        )
        data = json.loads(result)
        assert data["valid"] == False
        assert len(data["errors"]) >= 2

    @pytest.mark.asyncio
    async def test_validate_no_validations(self, executor):
        response = {"status": 200, "headers": {}, "body": {}}
        result = await executor.execute("validate_response", {"response": response})
        data = json.loads(result)
        assert data["valid"] == True
        assert len(data["errors"]) == 0
