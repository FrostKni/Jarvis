import base64
import os
from typing import Optional
from backend.config import get_settings


_settings = None
_cached_key = None


def _get_encryption_key() -> bytes:
    """Get or generate encryption key."""
    global _settings, _cached_key

    if _cached_key is not None:
        return _cached_key

    if _settings is None:
        _settings = get_settings()

    key = getattr(_settings, "encryption_key", None)
    if key:
        if isinstance(key, str):
            _cached_key = base64.urlsafe_b64decode(key.encode())
        else:
            _cached_key = key
    else:
        _cached_key = os.urandom(32)

    return _cached_key


def encrypt_data(data: str, key: bytes = None) -> str:
    """Encrypt sensitive data using Fernet symmetric encryption."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return data

    if not data:
        return data

    encryption_key = key or _get_encryption_key()

    if len(encryption_key) != 32:
        encryption_key = base64.urlsafe_b64decode(
            base64.urlsafe_b64encode(encryption_key[:32].ljust(32, b"\0"))
        )

    fernet_key = base64.urlsafe_b64encode(encryption_key)
    f = Fernet(fernet_key)

    encrypted = f.encrypt(data.encode("utf-8"))
    return base64.urlsafe_b64encode(encrypted).decode("utf-8")


def decrypt_data(encrypted: str, key: bytes = None) -> str:
    """Decrypt data that was encrypted with encrypt_data."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return encrypted

    if not encrypted:
        return encrypted

    encryption_key = key or _get_encryption_key()

    if len(encryption_key) != 32:
        encryption_key = base64.urlsafe_b64decode(
            base64.urlsafe_b64encode(encryption_key[:32].ljust(32, b"\0"))
        )

    fernet_key = base64.urlsafe_b64encode(encryption_key)
    f = Fernet(fernet_key)

    try:
        encrypted_bytes = base64.urlsafe_b64decode(encrypted.encode("utf-8"))
        decrypted = f.decrypt(encrypted_bytes)
        return decrypted.decode("utf-8")
    except Exception:
        return encrypted


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    try:
        import bcrypt
    except ImportError:
        import hashlib

        return hashlib.sha256(password.encode()).hexdigest()

    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a hash."""
    try:
        import bcrypt
    except ImportError:
        import hashlib

        return hashlib.sha256(password.encode()).hexdigest() == hashed

    try:
        return bcrypt.checkpw(password.encode(), hashed.encode("utf-8"))
    except Exception:
        return False
