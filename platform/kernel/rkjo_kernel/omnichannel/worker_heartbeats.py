"""OMNI-016.4.3 — tenant-scoped worker heartbeats.

Workers must explicitly bind to a tenant before publishing a heartbeat.
This table does not claim RabbitMQ queue depth or broker-wide health.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re

import psycopg


_WORKER_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{0,79}$")


@dataclass(frozen=True, slots=True)
class WorkerHeartbeat:
    tenant_id: str
    worker_name: str
    status: str
    last_seen_at: datetime
    stale: bool


class PostgreSQLOmnichannelWorkerHeartbeats:
    def __init__(self, database_url: str):
        if not database_url or not database_url.strip():
            raise ValueError("Database URL required.")
        self.database_url = database_url

    def initialize_schema(self) -> None:
        with psycopg.connect(self.database_url) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS omni_worker_heartbeats (
                  tenant_id TEXT NOT NULL,
                  worker_name TEXT NOT NULL,
                  status TEXT NOT NULL CHECK (status IN ('ready','degraded','stopped')),
                  last_seen_at TIMESTAMPTZ NOT NULL,
                  PRIMARY KEY (tenant_id, worker_name)
                )
            """)

    @staticmethod
    def _validate(tenant_id: str, worker_name: str | None = None):
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("Tenant binding required.")
        if worker_name is not None and not _WORKER_NAME.fullmatch(worker_name):
            raise ValueError("Invalid worker name.")

    def beat(self, *, tenant_id: str, worker_name: str, status: str,
             at: datetime | None = None) -> None:
        self._validate(tenant_id, worker_name)
        if status not in {"ready", "degraded", "stopped"}:
            raise ValueError("Invalid worker status.")
        at = datetime.now(timezone.utc) if at is None else at
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("Timezone-aware heartbeat required.")
        with psycopg.connect(self.database_url) as conn:
            conn.execute("""
                INSERT INTO omni_worker_heartbeats
                (tenant_id,worker_name,status,last_seen_at)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (tenant_id,worker_name) DO UPDATE SET
                  status=EXCLUDED.status,last_seen_at=EXCLUDED.last_seen_at
                WHERE omni_worker_heartbeats.last_seen_at <= EXCLUDED.last_seen_at
            """, (tenant_id, worker_name, status, at))

    def list(self, *, tenant_id: str, now: datetime | None = None,
             stale_after_seconds: int = 90) -> list[WorkerHeartbeat]:
        self._validate(tenant_id)
        now = datetime.now(timezone.utc) if now is None else now
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Timezone-aware timestamp required.")
        if not isinstance(stale_after_seconds, int) or isinstance(stale_after_seconds, bool) or not 1 <= stale_after_seconds <= 3600:
            raise ValueError("Invalid stale threshold.")
        with psycopg.connect(self.database_url) as conn:
            rows = conn.execute("""
                SELECT tenant_id,worker_name,status,last_seen_at
                FROM omni_worker_heartbeats WHERE tenant_id=%s
                ORDER BY worker_name
            """, (tenant_id,)).fetchall()
        cutoff = now - timedelta(seconds=stale_after_seconds)
        return [
            WorkerHeartbeat(t, name, status, last, last < cutoff)
            for t,name,status,last in rows
        ]
