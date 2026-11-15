"""Link storage and validation for the URL shortener."""

from __future__ import annotations

import re
import secrets
import sqlite3
import string
import threading
import time
from dataclasses import asdict, dataclass
from urllib.parse import quote, urlsplit

CODE_ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 7
MAX_URL_LENGTH = 2048
ALIAS_RE = re.compile(r"[A-Za-z0-9_-]{3,32}")
RESERVED_ALIASES = frozenset({"api"})

# Characters left untouched when percent-encoding non-ASCII parts of a URL.
_URL_SAFE = "%/:=&?~#+!$,;'@()*[]"


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
    created_at: int
    clicks: int

    def to_dict(self) -> dict:
        return asdict(self)


def validate_url(url: object) -> str:
    """Return a cleaned-up URL that is safe to redirect to, or raise InvalidURL."""
    if not isinstance(url, str):
        raise InvalidURL("url must be a string")
    url = url.strip()
    if not url:
        raise InvalidURL("url is required")
    if len(url) > MAX_URL_LENGTH:
        raise InvalidURL(f"url is longer than {MAX_URL_LENGTH} characters")
    if any(c.isspace() or ord(c) < 0x20 or ord(c) == 0x7F for c in url):
        raise InvalidURL("url must not contain whitespace or control characters")
    try:
        parts = urlsplit(url)
        hostname = parts.hostname
    except ValueError:
        raise InvalidURL("url is malformed") from None
    if parts.scheme not in ("http", "https"):
        raise InvalidURL("url must start with http:// or https://")
    if not hostname:
        raise InvalidURL("url must include a host")
    if not parts.netloc.isascii():
        raise InvalidURL("non-ASCII hostnames must be given in punycode form")
    # The URL ends up in a Location header, which has to be ASCII.
    return quote(url, safe=_URL_SAFE)


def validate_alias(alias: object) -> str:
    if not isinstance(alias, str) or not ALIAS_RE.fullmatch(alias):
        raise InvalidAlias(
            "alias must be 3-32 characters: letters, digits, '-' or '_'"
        )
    if alias.lower() in RESERVED_ALIASES:
        raise InvalidAlias(f"alias '{alias}' is reserved")
    return alias


def generate_code(length: int = CODE_LENGTH) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


class LinkStore:
    """SQLite-backed store. Safe to share between threads."""

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._lock = threading.Lock()
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS links (
                code       TEXT PRIMARY KEY,
                url        TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                clicks     INTEGER NOT NULL DEFAULT 0
            )
            """
        )

    def close(self) -> None:
        self._db.close()

    def create(self, url: object, alias: object = None) -> Link:
        """Shorten `url`, using `alias` as the code if one is given."""
        url = validate_url(url)
        now = int(time.time())
        if alias is not None:
            code = validate_alias(alias)
            if not self._insert(code, url, now):
                raise AliasTaken(f"alias '{code}' is already in use")
            return Link(code, url, now, 0)
        for _ in range(10):
            code = generate_code()
            if self._insert(code, url, now):
                return Link(code, url, now, 0)
        raise RuntimeError("could not generate a unique code")

    def get(self, code: str) -> Link | None:
        with self._lock:
            row = self._db.execute(
                "SELECT code, url, created_at, clicks FROM links WHERE code = ?",
                (code,),
            ).fetchone()
        return Link(*row) if row else None

    def resolve(self, code: str) -> str | None:
        """Return the target URL for `code` and count the visit."""
        with self._lock:
            row = self._db.execute(
                "SELECT url FROM links WHERE code = ?", (code,)
            ).fetchone()
            if row is None:
                return None
            self._db.execute(
                "UPDATE links SET clicks = clicks + 1 WHERE code = ?", (code,)
            )
        return row[0]

    def _insert(self, code: str, url: str, created_at: int) -> bool:
        with self._lock:
            try:
                self._db.execute(
                    "INSERT INTO links (code, url, created_at) VALUES (?, ?, ?)",
                    (code, url, created_at),
                )
            except sqlite3.IntegrityError:
                return False
        return True
