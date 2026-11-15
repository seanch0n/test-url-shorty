"""Runtime configuration, read from environment variables."""

import os
from dataclasses import dataclass

DEFAULT_DATABASE_PATH = "shorty.db"


@dataclass(frozen=True)
class DatabaseConfig:
    path: str = DEFAULT_DATABASE_PATH
    timeout: float = 2.0

    @classmethod
    def from_env(cls, environ=None) -> "DatabaseConfig":
        env = os.environ if environ is None else environ
        return cls(
            path=env.get("SHORTY_DATABASE_PATH", DEFAULT_DATABASE_PATH),
            timeout=float(env.get("SHORTY_DATABASE_TIMEOUT", "2.0")),
        )
