"""Validation of destination URLs and request fields."""

from datetime import datetime
from urllib.parse import urlsplit

ALLOWED_SCHEMES = frozenset({"http", "https"})
MAX_URL_LENGTH = 2048


class ValidationError(ValueError):
    """Invalid client input. `code` is a stable machine-readable identifier."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def validate_destination_url(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("invalid_url", "url is required and must be a string")
    url = value.strip()
    if len(url) > MAX_URL_LENGTH:
        raise ValidationError(
            "invalid_url", f"url must be at most {MAX_URL_LENGTH} characters"
        )
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in url):
        raise ValidationError("invalid_url", "url must not contain whitespace or control characters")
    try:
        parts = urlsplit(url)
        hostname = parts.hostname
        parts.port  # raises ValueError for a malformed port
    except ValueError:
        raise ValidationError("invalid_url", "url is malformed") from None
    if not parts.scheme:
        raise ValidationError("invalid_url", "url must be absolute, including http:// or https://")
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValidationError(
            "unsupported_scheme", "only http and https urls can be shortened"
        )
    if not hostname:
        raise ValidationError("invalid_url", "url must include a host")
    return url


def parse_expires_at(value) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("invalid_expires_at", "expires_at must be an ISO 8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValidationError("invalid_expires_at", "expires_at must be an ISO 8601 string") from None
    if parsed.tzinfo is None:
        raise ValidationError(
            "invalid_expires_at", "expires_at must include a timezone, e.g. 2030-01-01T00:00:00Z"
        )
    return parsed
