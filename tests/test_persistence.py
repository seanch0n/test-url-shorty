from datetime import datetime, timedelta, timezone

import pytest

from shorty.config import DatabaseConfig
from shorty.db import connect, migrate
from shorty.repository import DuplicateShortCodeError, LinkRepository


@pytest.fixture
def conn(tmp_path):
    c = connect(DatabaseConfig(path=str(tmp_path / "test.db")))
    migrate(c)
    yield c
    c.close()


@pytest.fixture
def repo(conn):
    return LinkRepository(conn)


def test_migrate_creates_schema_and_is_idempotent(tmp_path):
    c = connect(DatabaseConfig(path=str(tmp_path / "m.db")))
    assert migrate(c) == ["0001_create_links.sql"]
    assert migrate(c) == []
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"links", "schema_migrations"} <= tables


def test_short_code_has_unique_index(conn):
    indexes = conn.execute("PRAGMA index_list('links')").fetchall()
    by_name = {r["name"]: r for r in indexes}
    assert by_name["idx_links_short_code"]["unique"] == 1
    plan = conn.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM links WHERE short_code = 'x'"
    ).fetchall()
    assert any("idx_links_short_code" in r["detail"] for r in plan)


def test_create_and_retrieve(repo):
    link = repo.create("abc1234", "https://example.com/a?b=1")
    assert link.id is not None
    assert link.created_at.tzinfo is not None
    fetched = repo.get_by_code("abc1234")
    assert fetched == link
    assert fetched.target_url == "https://example.com/a?b=1"
    assert fetched.is_usable()


def test_get_unknown_code_returns_none(repo):
    assert repo.get_by_code("nope") is None
    assert repo.code_exists("nope") is False


def test_duplicate_short_code_rejected(repo):
    repo.create("dup0001", "https://a.example")
    with pytest.raises(DuplicateShortCodeError):
        repo.create("dup0001", "https://b.example")
    assert repo.get_by_code("dup0001").target_url == "https://a.example"


def test_short_codes_are_case_sensitive(repo):
    repo.create("AbCdEfG", "https://a.example")
    repo.create("abcdefg", "https://b.example")
    assert repo.get_by_code("AbCdEfG").target_url == "https://a.example"


def test_duplicate_destination_allowed(repo):
    repo.create("one0001", "https://same.example")
    repo.create("two0002", "https://same.example")


def test_expired_links_identified(repo):
    now = datetime.now(timezone.utc)
    past = repo.create("old0001", "https://a.example", expires_at=now - timedelta(minutes=1))
    future = repo.create("new0001", "https://b.example", expires_at=now + timedelta(days=1))
    assert past.is_expired()
    assert not past.is_usable()
    assert not future.is_expired()
    assert [l.short_code for l in repo.list_unusable()] == ["old0001"]


def test_disabled_links_identified(repo):
    repo.create("dis0001", "https://a.example")
    assert repo.set_disabled("dis0001")
    link = repo.get_by_code("dis0001")
    assert link.disabled
    assert not link.is_usable()
    assert [l.short_code for l in repo.list_unusable()] == ["dis0001"]
    assert repo.set_disabled("missing") is False


def test_naive_datetime_rejected(repo):
    with pytest.raises(ValueError):
        repo.create("naive01", "https://a.example", expires_at=datetime(2030, 1, 1))


def test_config_from_env():
    cfg = DatabaseConfig.from_env(
        {"SHORTY_DATABASE_PATH": "/tmp/x.db", "SHORTY_DATABASE_TIMEOUT": "2.5"}
    )
    assert cfg == DatabaseConfig(path="/tmp/x.db", timeout=2.5)
    assert DatabaseConfig.from_env({}).path == "shorty.db"
