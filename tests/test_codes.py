import re

import pytest

from shorty.codes import (
    BASE62_ALPHABET,
    AliasTakenError,
    CodeGenerationError,
    InvalidAliasError,
    ShortCodeService,
    generate_code,
    validate_alias,
)
from shorty.config import DatabaseConfig
from shorty.db import connect, migrate
from shorty.repository import LinkRepository


@pytest.fixture
def repo(tmp_path):
    conn = connect(DatabaseConfig(path=str(tmp_path / "codes.db")))
    migrate(conn)
    yield LinkRepository(conn)
    conn.close()


def scripted(*codes):
    """A generator that returns the given codes in order."""
    it = iter(codes)
    return lambda length: next(it)


def test_alphabet_is_base62():
    assert len(BASE62_ALPHABET) == 62
    assert len(set(BASE62_ALPHABET)) == 62


def test_generated_codes_are_url_safe_and_default_length():
    for _ in range(500):
        code = generate_code()
        assert len(code) == 7
        assert re.fullmatch(r"[0-9A-Za-z]+", code)


def test_generate_code_respects_length():
    assert len(generate_code(8)) == 8
    with pytest.raises(ValueError):
        generate_code(0)


def test_generated_codes_are_unique_when_persisted(repo):
    service = ShortCodeService(repo)
    codes = {service.shorten("https://example.com").short_code for _ in range(300)}
    assert len(codes) == 300


def test_retries_after_collision(repo):
    repo.create("taken01", "https://first.example")
    service = ShortCodeService(repo, generator=scripted("taken01", "free001"))
    link = service.shorten("https://second.example")
    assert link.short_code == "free001"
    assert repo.get_by_code("taken01").target_url == "https://first.example"


def test_retries_when_insert_races(repo, monkeypatch):
    # Pre-check says free, but another writer inserts first.
    service = ShortCodeService(repo, generator=scripted("racy001", "free002"))
    real_create = repo.create

    def create_once_taken(code, url, expires_at=None):
        if code == "racy001" and not repo.code_exists(code):
            real_create(code, "https://other.example")
        return real_create(code, url, expires_at=expires_at)

    monkeypatch.setattr(repo, "create", create_once_taken)
    assert service.shorten("https://mine.example").short_code == "free002"


def test_gives_up_after_max_attempts(repo):
    repo.create("always1", "https://a.example")
    service = ShortCodeService(
        repo, max_attempts=3, generator=lambda n: "always1"
    )
    with pytest.raises(CodeGenerationError):
        service.shorten("https://b.example")


def test_custom_alias_is_used(repo):
    link = ShortCodeService(repo).shorten("https://a.example", alias="my-link_1")
    assert link.short_code == "my-link_1"


def test_taken_alias_is_rejected_without_retry(repo):
    service = ShortCodeService(repo)
    service.shorten("https://a.example", alias="promo")
    with pytest.raises(AliasTakenError):
        service.shorten("https://b.example", alias="promo")


@pytest.mark.parametrize(
    "alias",
    ["ab", "x" * 33, "has space", "slash/es", "dot.s", "ünïcode", "", "API", "health"],
)
def test_invalid_aliases_rejected(alias):
    with pytest.raises(InvalidAliasError):
        validate_alias(alias)


@pytest.mark.parametrize("alias", ["abc", "My-Link", "under_score", "x" * 32])
def test_valid_aliases_accepted(alias):
    assert validate_alias(alias) == alias
