"""Read-only Impala SQL execution for configurable data quality checks."""

from contextlib import closing

from impala.dbapi import connect

from .config import get_settings


class ImpalaClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.host = settings.impala_host
        self.port = settings.impala_port
        self.database = settings.impala_database
        self.user = settings.impala_user
        self.password = settings.impala_password
        self.auth_mechanism = settings.impala_auth_mechanism

    def scalar(self, sql: str) -> float:
        """Execute a single read-only query and return the first scalar value."""
        if not self.host:
            raise RuntimeError("IMPALA_HOST is not configured")
        with closing(
            connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                auth_mechanism=self.auth_mechanism,
            )
        ) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(sql)
                row = cursor.fetchone()
                if not row:
                    raise ValueError("Impala check query returned no rows")
                return float(row[0])
