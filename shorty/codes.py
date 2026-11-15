"""Short code generation and custom alias validation."""

import re
import secrets
import string
from collections.abc import Callable
from datetime import datetime

from shorty.repository import DuplicateShortCodeError, Link, LinkRepository

BASE62_ALPHABET = string.digits + string.ascii_letters
DEFAULT_CODE_LENGTH = 7
DEFAULT_MAX_ATTEMPTS = 5

ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
# Aliases that would shadow application routes or look official.
RESERVED_ALIASES = frozenset({"api", "admin", "static", "health", "login", "logout", "signup"})


class InvalidAliasError(ValueError):
    """A user-supplied alias is malformed or reserved."""


class AliasTakenError(Exception):
    def __init__(self, alias: str):
        super().__init__(f"alias already in use: {alias}")
        self.alias = alias


class CodeGenerationError(Exception):
    """No free short code was found within the attempt limit."""


def generate_code(length: int = DEFAULT_CODE_LENGTH) -> str:
    """A random Base62 code from a cryptographically secure source."""
    if length < 1:
        raise ValueError("length must be positive")
    return "".join(secrets.choice(BASE62_ALPHABET) for _ in range(length))


def validate_alias(alias: str) -> str:
    if not ALIAS_PATTERN.fullmatch(alias):
        raise InvalidAliasError(
            "alias must be 3-32 characters of letters, digits, '-' or '_'"
        )
    if alias.lower() in RESERVED_ALIASES:
        raise InvalidAliasError(f"alias is reserved: {alias}")
    return alias


class ShortCodeService:
    def __init__(
        self,
        repo: LinkRepository,
        length: int = DEFAULT_CODE_LENGTH,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        generator: Callable[[int], str] = generate_code,
    ):
        self.repo = repo
        self.length = length
        self.max_attempts = max_attempts
        self.generator = generator

    def shorten(
        self,
        target_url: str,
        alias: str | None = None,
        expires_at: datetime | None = None,
    ) -> Link:
        if alias is not None:
            return self._create_with_alias(target_url, alias, expires_at)
        return self._create_with_generated_code(target_url, expires_at)

    def _create_with_alias(self, target_url, alias, expires_at) -> Link:
        validate_alias(alias)
        try:
            return self.repo.create(alias, target_url, expires_at=expires_at)
        except DuplicateShortCodeError as exc:
            raise AliasTakenError(alias) from exc

    def _create_with_generated_code(self, target_url, expires_at) -> Link:
        for _ in range(self.max_attempts):
            code = self.generator(self.length)
            # Cheap pre-check; the unique index still catches a concurrent insert.
            if self.repo.code_exists(code):
                continue
            try:
                return self.repo.create(code, target_url, expires_at=expires_at)
            except DuplicateShortCodeError:
                continue
        raise CodeGenerationError(
            f"no free short code after {self.max_attempts} attempts"
        )
