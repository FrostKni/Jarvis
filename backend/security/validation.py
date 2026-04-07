import os
import re
from pathlib import Path
from typing import Tuple

DANGEROUS_PATTERNS = [
    (r"\.\.[\\/]", "Path traversal attempt"),
    (r"[;&|`$]", "Shell injection characters"),
    (r"<script", "XSS attempt"),
    (r"javascript:", "JavaScript protocol"),
    (r"on\w+\s*=", "Event handler injection"),
    (r"eval\s*\(", "eval() call"),
    (r"exec\s*\(", "exec() call"),
    (r"__import__", "Dynamic import"),
]

MAX_INPUT_LENGTH = 100000


def validate_input(text: str, max_length: int = MAX_INPUT_LENGTH) -> Tuple[bool, str]:
    """Validate user input for security.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if text is None:
        return True, ""

    if not isinstance(text, str):
        return False, "Input must be a string"

    if len(text) > max_length:
        return False, f"Input exceeds maximum length of {max_length} characters"

    text_lower = text.lower()

    for pattern, description in DANGEROUS_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return False, f"Potentially dangerous input detected: {description}"

    return True, ""


def sanitize_path(path: str, base_dir: str) -> str:
    """Sanitize and validate a file path.

    Ensures the resolved path is within the base directory.

    Args:
        path: The path to sanitize
        base_dir: The allowed base directory

    Returns:
        The sanitized absolute path

    Raises:
        ValueError: If path escapes base directory
    """
    if not path:
        raise ValueError("Path cannot be empty")

    if not base_dir:
        raise ValueError("Base directory cannot be empty")

    base_path = Path(base_dir).resolve()

    sanitized = Path(path)
    if not sanitized.is_absolute():
        sanitized = base_path / sanitized

    try:
        resolved = sanitized.resolve()
    except Exception as e:
        raise ValueError(f"Invalid path: {e}")

    try:
        resolved.relative_to(base_path)
    except ValueError:
        raise ValueError(f"Path '{path}' escapes base directory '{base_dir}'")

    return str(resolved)


def validate_email(email: str) -> Tuple[bool, str]:
    """Validate email format."""
    if not email:
        return False, "Email cannot be empty"

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        return False, "Invalid email format"

    return True, ""


def validate_url(url: str, allowed_schemes: list = None) -> Tuple[bool, str]:
    """Validate URL format and scheme."""
    if not url:
        return False, "URL cannot be empty"

    allowed_schemes = allowed_schemes or ["http", "https"]

    scheme_pattern = r"^([a-zA-Z]+):"
    match = re.match(scheme_pattern, url)

    if not match:
        return False, "URL must have a scheme"

    scheme = match.group(1).lower()
    if scheme not in allowed_schemes:
        return False, f"URL scheme '{scheme}' not allowed. Allowed: {allowed_schemes}"

    dangerous_patterns = [
        r"javascript:",
        r"data:",
        r"vbscript:",
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return False, f"Potentially dangerous URL scheme detected"

    return True, ""


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename by removing/replacing dangerous characters."""
    if not filename:
        return "unnamed"

    filename = os.path.basename(filename)

    dangerous_chars = ["<", ">", ":", '"', "|", "?", "*", "\\", "/"]
    for char in dangerous_chars:
        filename = filename.replace(char, "_")

    filename = re.sub(r"\.\.", "_", filename)
    filename = re.sub(r"\s+", "_", filename)
    filename = filename.strip("._")

    if not filename:
        return "unnamed"

    return filename


def validate_json_size(data: str, max_size_kb: int = 1024) -> Tuple[bool, str]:
    """Validate JSON data size."""
    if not data:
        return True, ""

    size_kb = len(data.encode("utf-8")) / 1024
    if size_kb > max_size_kb:
        return False, f"JSON data exceeds {max_size_kb}KB limit"

    return True, ""
