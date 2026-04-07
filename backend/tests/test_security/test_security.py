import pytest
import pytest_asyncio
import asyncio
from backend.security.audit import AuditLogger
from backend.security.encryption import (
    encrypt_data,
    decrypt_data,
    hash_password,
    verify_password,
)
from backend.security.validation import (
    validate_input,
    sanitize_path,
    validate_email,
    validate_url,
    sanitize_filename,
    validate_json_size,
)
from backend.memory.store import PersistentStore


class TestAuditLogger:
    @pytest_asyncio.fixture
    async def store(self, tmp_path):
        store = PersistentStore()
        store._db_path = str(tmp_path / "test.db")
        await store.init()
        return store

    @pytest_asyncio.fixture
    async def audit(self, store):
        return AuditLogger(store)

    @pytest.mark.asyncio
    async def test_log_event(self, audit):
        await audit.log_event("test_event", {"key": "value"})
        events = await audit.get_events(limit=10)
        assert len(events) == 1
        assert events[0]["event_type"] == "test_event"
        assert events[0]["details"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_log_tool_execution(self, audit):
        await audit.log_tool_execution("read_file", {"path": "/tmp"}, "content", True)
        events = await audit.get_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "tool_execution"
        assert events[0]["details"]["tool"] == "read_file"
        assert events[0]["severity"] == "info"

    @pytest.mark.asyncio
    async def test_log_authentication(self, audit):
        await audit.log_authentication("user123", "login", True, "127.0.0.1")
        events = await audit.get_events()
        assert events[0]["event_type"] == "authentication"
        assert events[0]["details"]["success"] is True


class TestEncryption:
    def test_encrypt_decrypt_cycle(self):
        original = "secret data"
        encrypted = encrypt_data(original)
        decrypted = decrypt_data(encrypted)
        assert decrypted == original

    def test_encrypt_produces_different_output(self):
        data = "test"
        encrypted1 = encrypt_data(data)
        encrypted2 = encrypt_data(data)
        assert encrypted1 != encrypted2

    def test_encrypt_empty_string(self):
        assert encrypt_data("") == ""

    def test_decrypt_empty_string(self):
        assert decrypt_data("") == ""

    def test_hash_password(self):
        password = "mypassword"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("wrong", hashed) is False


class TestValidation:
    def test_validate_input_valid(self):
        valid, error = validate_input("normal input")
        assert valid is True
        assert error == ""

    def test_validate_input_too_long(self):
        long_input = "a" * 200000
        valid, error = validate_input(long_input, max_length=100000)
        assert valid is False
        assert "exceeds maximum length" in error

    def test_validate_input_path_traversal(self):
        valid, error = validate_input("../../etc/passwd")
        assert valid is False
        assert "Path traversal" in error

    def test_validate_input_shell_injection(self):
        valid, error = validate_input("test; rm -rf /")
        assert valid is False
        assert "Shell injection" in error

    def test_validate_input_xss(self):
        valid, error = validate_input("<script>alert('xss')</script>")
        assert valid is False
        assert "XSS" in error

    def test_sanitize_path_valid(self, tmp_path):
        base = str(tmp_path)
        result = sanitize_path("subdir/file.txt", base)
        assert base in result
        assert "subdir" in result

    def test_sanitize_path_traversal_attack(self, tmp_path):
        base = str(tmp_path)
        with pytest.raises(ValueError, match="escapes base directory"):
            sanitize_path("../../etc/passwd", base)

    def test_sanitize_path_empty(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            sanitize_path("", "/tmp")

    def test_validate_email_valid(self):
        valid, error = validate_email("user@example.com")
        assert valid is True

    def test_validate_email_invalid(self):
        valid, error = validate_email("not-an-email")
        assert valid is False

    def test_validate_url_valid(self):
        valid, error = validate_url("https://example.com")
        assert valid is True

    def test_validate_url_invalid_scheme(self):
        valid, error = validate_url("ftp://example.com")
        assert valid is False

    def test_validate_url_javascript(self):
        valid, error = validate_url("javascript:alert(1)")
        assert valid is False

    def test_sanitize_filename_dangerous_chars(self):
        result = sanitize_filename("test<>file.txt")
        assert "<" not in result
        assert ">" not in result

    def test_sanitize_filename_empty(self):
        assert sanitize_filename("") == "unnamed"

    def test_validate_json_size(self):
        valid, _ = validate_json_size('{"small": "data"}')
        assert valid is True

        large_json = '{"data": "' + "x" * 2000000 + '"}'
        valid, error = validate_json_size(large_json, max_size_kb=100)
        assert valid is False
