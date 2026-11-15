"""SQLite connection handling and a minimal forward-only migration runner."""

import sqlite3
from importlib import resources

from shorty.config import DatabaseConfig


def connect(config: DatabaseConfig) -> sqlite3.Connection:
    conn = sqlite3.connect(config.path, timeout=config.timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL lets readers (redirects) proceed while a write is in progress.
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _migration_files():
    folder = resources.files("shorty") / "migrations"
    files = [f for f in folder.iterdir() if f.name.endswith(".sql")]
    return sorted(files, key=lambda f: f.name)


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Apply every migration not yet recorded. Returns the names applied."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " name TEXT PRIMARY KEY,"
        " applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))"
    )
    done = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
    applied = []
    for migration in _migration_files():
        if migration.name in done:
            continue
        # executescript commits any open transaction first, so wrap each
        # migration in its own explicit transaction to keep it atomic.
        conn.executescript(
            "BEGIN;\n"
            + migration.read_text(encoding="utf-8")
            + f"\nINSERT INTO schema_migrations (name) VALUES ('{migration.name}');\nCOMMIT;"
        )
        applied.append(migration.name)
    return applied
