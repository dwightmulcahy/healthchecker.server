"""SQLite-backed persistence for monitored application configuration."""

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class MonitorConfig:
    """Configuration needed to recreate a monitoring job after restart."""

    appname: str
    url: str
    email: str
    timeout: int
    interval: int
    unhealthy_threshold: int
    healthy_threshold: int
    paused: bool = False


class MonitorStore:
    """Store monitoring configuration in a small transactional SQLite database.

    Args:
        filename: SQLite database file path; ':memory:' is supported for
            individual operations but not shared between separate connections.
    """

    def __init__(self, filename):
        self.filename = str(filename)
        if self.filename != ":memory:":
            Path(self.filename).parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS monitors ("
                "appname TEXT PRIMARY KEY, url TEXT NOT NULL, email TEXT NOT NULL, "
                "timeout INTEGER NOT NULL, interval INTEGER NOT NULL, "
                "unhealthy_threshold INTEGER NOT NULL, "
                "healthy_threshold INTEGER NOT NULL, "
                "paused INTEGER NOT NULL DEFAULT 0)"
            )

    def _connection(self):
        """Return a database connection in a closing context."""
        return closing(sqlite3.connect(self.filename, timeout=10))

    def upsert(self, config):
        """Create or update a monitored application configuration.

        Args:
            config: MonitorConfig to persist.
        """
        with self._connection() as conn:
            with conn:
                conn.execute(
                    "INSERT INTO monitors VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(appname) DO UPDATE SET "
                    "url=excluded.url, email=excluded.email, timeout=excluded.timeout, "
                    "interval=excluded.interval, unhealthy_threshold=excluded.unhealthy_threshold, "
                    "healthy_threshold=excluded.healthy_threshold, paused=excluded.paused",
                    (config.appname, config.url, config.email, config.timeout,
                     config.interval, config.unhealthy_threshold,
                     config.healthy_threshold, int(config.paused)),
                )

    def remove(self, appname):
        """Delete a monitoring registration.

        Args:
            appname: Registered application identifier.
        """
        with self._connection() as conn:
            with conn:
                conn.execute("DELETE FROM monitors WHERE appname=?", (appname,))

    def set_paused(self, appname, paused):
        """Persist the scheduled pause state of an application.

        Args:
            appname: Registered application identifier.
            paused: Whether to pause monitoring after restart.
        """
        with self._connection() as conn:
            with conn:
                conn.execute(
                    "UPDATE monitors SET paused=? WHERE appname=?",
                    (int(paused), appname),
                )

    def list(self):
        """Return all monitoring registrations in a stable order.

        Returns:
            List of MonitorConfig records.
        """
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT appname, url, email, timeout, interval, "
                "unhealthy_threshold, healthy_threshold, paused "
                "FROM monitors ORDER BY appname"
            ).fetchall()
        return [MonitorConfig(*row[:7], paused=bool(row[7])) for row in rows]
