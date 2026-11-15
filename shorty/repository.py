"""Database access for shortened links."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


class DuplicateShortCodeError(Exception):
    """Raised when a short code is already taken."""

    def __init__(self, short_code: str):
        super().__init__(f"short code already exists: {short_code}")
        self.short_code = short_code


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_db(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("datetimes must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _from_db(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


@dataclass(frozen=True)
class Link:
    id: int
    short_code: str
    target_url: str
    created_at: datetime
    expires_at: datetime | None
    disabled: bool

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        return (now or _utcnow()) >= self.expires_at

    def is_usable(self, now: datetime | None = None) -> bool:
        return not self.disabled and not self.is_expired(now)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Link":
        return cls(
            id=row["id"],
            short_code=row["short_code"],
            target_url=row["target_url"],
            created_at=_from_db(row["created_at"]),
            expires_at=_from_db(row["expires_at"]),
            disabled=bool(row["disabled"]),
        )


class LinkRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(
        self,
        short_code: str,
        target_url: str,
        expires_at: datetime | None = None,
    ) -> Link:
        try:
            with self.conn:
                cur = self.conn.execute(
                    "INSERT INTO links (short_code, target_url, created_at, expires_at)"
                    " VALUES (?, ?, ?, ?)",
                    (short_code, target_url, _to_db(_utcnow()), _to_db(expires_at)),
                )
        except sqlite3.IntegrityError as exc:
            if "links.short_code" in str(exc):
                raise DuplicateShortCodeError(short_code) from exc
            raise
        return self.get_by_id(cur.lastrowid)

    def get_by_id(self, link_id: int) -> Link | None:
        row = self.conn.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()
        return Link.from_row(row) if row else None

    def get_by_code(self, short_code: str) -> Link | None:
        row = self.conn.execute(
            "SELECT * FROM links WHERE short_code = ?", (short_code,)
        ).fetchone()
        return Link.from_row(row) if row else None

    def code_exists(self, short_code: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM links WHERE short_code = ?", (short_code,)
        ).fetchone()
        return row is not None

    def set_disabled(self, short_code: str, disabled: bool = True) -> bool:
        with self.conn:
            cur = self.conn.execute(
                "UPDATE links SET disabled = ? WHERE short_code = ?",
                (int(disabled), short_code),
            )
        return cur.rowcount > 0

    def list_unusable(self, now: datetime | None = None) -> list[Link]:
        """Links that are disabled or past their expiry."""
        rows = self.conn.execute(
            "SELECT * FROM links WHERE disabled = 1"
            " OR (expires_at IS NOT NULL AND expires_at <= ?) ORDER BY id",
            (_to_db(now or _utcnow()),),
        ).fetchall()
        return [Link.from_row(r) for r in rows]
