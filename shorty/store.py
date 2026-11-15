"""SQLite-backed storage for short links."""

from __future__ import annotations

import re
import secrets
import sqlite3
import string
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator
from urllib.parse import urlsplit

ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 7
MAX_URL_LENGTH = 2048

_ALIAS_RE = re.compile(r"[A-Za-z0-9_-]{3,32}")
# Single-segment paths the app serves itself; an alias with one of these names
# would be unreachable.
_RESERVED = frozenset({"api", "docs", "redoc"})
_CODE_ATTEMPTS = 10


class InvalidURL(ValueError):
    pass


class InvalidAlias(ValueError):
    pass


class AliasTaken(Exception):
    pass


@dataclass(frozen=True)
class Link:
    code: str
    url: str
    created_at: str
    clicks: int


def validate_url(url: str) -> str:
    """Return the trimmed URL, or raise InvalidURL if we should not redirect to it."""
    url = url.strip()
    if not url:
        raise InvalidURL("url is empty")
    if len(url) > MAX_URL_LENGTH:
        raise InvalidURL(f"url is longer than {MAX_URL_LENGTH} characters")
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in url):
        raise InvalidURL("url contains whitespace or control characters")
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        raise InvalidURL("url is malformed") from None
    if parts.scheme.lower() not in ("http", "https"):
        raise InvalidURL("url must start with http:// or https://")
    if not host:
        raise InvalidURL("url has no host")
    return url


def validate_alias(alias: str) -> str:
    if not _ALIAS_RE.fullmatch(alias):
        raise InvalidAlias(
            "alias must be 3-32 characters from letters, digits, '-' and '_'"
        )
    if alias.lower() in _RESERVED:
        raise InvalidAlias(f"alias '{alias}' is reserved")
    return alias


def _random_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


class LinkStore:
    def __init__(self, path: str) -> None:
        self._path = path
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS links (
                    code       TEXT PRIMARY KEY,
                    url        TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    clicks     INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            with conn:  # commit on success, roll back on error
                yield conn
        finally:
            conn.close()

    def create(self, url: str, alias: str | None = None) -> Link:
        url = validate_url(url)
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if alias is not None:
            code = validate_alias(alias)
            if not self._insert(code, url, created_at):
                raise AliasTaken(f"alias '{code}' is already in use")
            return Link(code, url, created_at, 0)
        for _ in range(_CODE_ATTEMPTS):
            code = _random_code()
            if self._insert(code, url, created_at):
                return Link(code, url, created_at, 0)
        raise RuntimeError("could not generate an unused code")

    def _insert(self, code: str, url: str, created_at: str) -> bool:
        try:
            with self._connect() as db:
                db.execute(
                    "INSERT INTO links (code, url, created_at) VALUES (?, ?, ?)",
                    (code, url, created_at),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def get(self, code: str) -> Link | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT code, url, created_at, clicks FROM links WHERE code = ?",
                (code,),
            ).fetchone()
        return Link(**row) if row else None

    def resolve(self, code: str) -> str | None:
        """Return the target URL and count the click, or None if unknown."""
        with self._connect() as db:
            row = db.execute(
                "UPDATE links SET clicks = clicks + 1 WHERE code = ? RETURNING url",
                (code,),
            ).fetchone()
        return row["url"] if row else None
