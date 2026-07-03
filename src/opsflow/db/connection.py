"""Database connection settings and helpers (P1).

Connection settings come from OPSFLOW_DB_* environment variables with defaults that
match docker-compose.yml — synthetic local-dev values only, never real credentials.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DbSettings:
    host: str = "localhost"
    port: int = 5432
    dbname: str = "opsflow"
    user: str = "opsflow"
    password: str = "opsflow_local_dev"

    @classmethod
    def from_env(cls) -> "DbSettings":
        return cls(
            host=os.environ.get("OPSFLOW_DB_HOST", cls.host),
            port=int(os.environ.get("OPSFLOW_DB_PORT", cls.port)),
            dbname=os.environ.get("OPSFLOW_DB_NAME", cls.dbname),
            user=os.environ.get("OPSFLOW_DB_USER", cls.user),
            password=os.environ.get("OPSFLOW_DB_PASSWORD", cls.password),
        )

    def conninfo(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.dbname} "
            f"user={self.user} password={self.password}"
        )


def connect(settings: DbSettings | None = None):
    """Open a psycopg connection. Imported lazily so P0 never needs psycopg."""
    import psycopg

    settings = settings or DbSettings.from_env()
    return psycopg.connect(settings.conninfo())
