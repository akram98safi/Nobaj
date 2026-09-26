"""Small persistent analytics store backed by SQLite.

The app intentionally keeps analytics first-party and lightweight. No raw IP
addresses are stored; a random, long-lived visitor cookie is used to estimate
unique visitors.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from backend.app.core.constants import DATA_DIR


class AnalyticsStore:
    """Thread-safe-enough SQLite store using one short-lived connection per call."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DATA_DIR / "analytics.sqlite3"

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS visits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    visitor_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    visited_at TEXT NOT NULL,
                    user_agent TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_visits_visited_at
                    ON visits(visited_at);
                CREATE INDEX IF NOT EXISTS idx_visits_visitor_id
                    ON visits(visitor_id);

                CREATE TABLE IF NOT EXISTS operations (
                    job_id TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    input_bytes INTEGER DEFAULT 0,
                    output_bytes INTEGER DEFAULT 0,
                    error_message TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_operations_created_at
                    ON operations(created_at);
                CREATE INDEX IF NOT EXISTS idx_operations_status
                    ON operations(status);
                """
            )

    def record_visit(self, visitor_id: str, path: str, user_agent: str = "") -> None:
        if not visitor_id:
            return
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO visits (visitor_id, path, visited_at, user_agent)
                VALUES (?, ?, ?, ?)
                """,
                (visitor_id, path, self._now(), user_agent[:240]),
            )

    def record_operation_started(self, job_id: str, operation: str, input_bytes: int = 0) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT OR IGNORE INTO operations
                (job_id, operation, status, created_at, input_bytes)
                VALUES (?, ?, 'queued', ?, ?)
                """,
                (job_id, operation, self._now(), int(input_bytes or 0)),
            )

    def record_operation_finished(
        self,
        job_id: str,
        status: str,
        output_bytes: int = 0,
        error_message: str | None = None,
    ) -> None:
        with self._connect() as db:
            db.execute(
                """
                UPDATE operations
                SET status = ?, completed_at = ?, output_bytes = ?, error_message = ?
                WHERE job_id = ?
                """,
                (status, self._now(), int(output_bytes or 0), (error_message or "")[:500], job_id),
            )

    def public_stats(self) -> Dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT
                    COUNT(DISTINCT visitor_id) AS total_visitors,
                    COUNT(DISTINCT CASE WHEN date(visited_at) = date('now') THEN visitor_id END) AS today_visitors
                FROM visits
                """
            ).fetchone()
            ops = db.execute(
                """
                SELECT
                    COUNT(*) AS total_operations,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_operations,
                    COALESCE(SUM(CASE WHEN status = 'completed' THEN output_bytes ELSE 0 END), 0) AS output_bytes
                FROM operations
                """
            ).fetchone()
        return {
            "total_visitors": int(row["total_visitors"] or 0),
            "today_visitors": int(row["today_visitors"] or 0),
            "total_operations": int(ops["total_operations"] or 0),
            "completed_operations": int(ops["completed_operations"] or 0),
            "processed_bytes": int(ops["output_bytes"] or 0),
        }

    def admin_stats(self) -> Dict[str, Any]:
        public = self.public_stats()
        with self._connect() as db:
            operation_rows = db.execute(
                """
                SELECT operation,
                       COUNT(*) AS total,
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                       SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
                FROM operations
                GROUP BY operation
                ORDER BY total DESC
                """
            ).fetchall()
            daily_rows = db.execute(
                """
                SELECT date(visited_at) AS day,
                       COUNT(*) AS visits,
                       COUNT(DISTINCT visitor_id) AS unique_visitors
                FROM visits
                WHERE visited_at >= datetime('now', '-29 days')
                GROUP BY date(visited_at)
                ORDER BY day ASC
                """
            ).fetchall()
        return {
            **public,
            "operations_by_type": [dict(row) for row in operation_rows],
            "daily_visits": [dict(row) for row in daily_rows],
            "database": str(self.db_path.name),
        }

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")


analytics = AnalyticsStore()
