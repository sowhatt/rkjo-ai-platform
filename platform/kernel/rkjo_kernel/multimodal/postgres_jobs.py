"""PostgreSQL job persistence using RKJO's existing transactional workflow outbox."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import psycopg

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.multimodal.jobs import IngestionJob, JobStatus
from rkjo_kernel.workflow.outbox import OutboxMessage
from rkjo_kernel.workflow.postgres_unit_of_work import PostgreSQLTransactionalOutboxStore


_FIELDS = """job_id, tenant_id, idempotency_key, channel, recipient_ref,
correlation_id, mission_id, trace_id, status, version"""


def _job(row: tuple) -> IngestionJob:
    return IngestionJob(
        job_id=row[0], tenant_id=row[1], idempotency_key=row[2],
        channel=row[3], recipient_ref=row[4], correlation_id=row[5],
        mission_id=row[6], trace_id=row[7],
        status=JobStatus(row[8]), version=row[9],
    )


class PostgreSQLIngestionJobAdapter:
    """Atomic job state + outbox event; no new event queue or publisher."""

    def __init__(self, database_url: str, *, event_queue: str = "rkjo.multimodal.jobs") -> None:
        if not database_url.strip() or not event_queue.strip():
            raise ValueError("Database URL and event queue are required.")
        self.database_url = database_url
        self.event_queue = event_queue

    def initialize_schema(self) -> None:
        """Call explicitly after the existing workflow schema bootstrap."""
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS multimodal_ingestion_jobs (
                        job_id TEXT PRIMARY KEY,
                        tenant_id TEXT NOT NULL,
                        idempotency_key TEXT NOT NULL,
                        channel TEXT NOT NULL,
                        recipient_ref TEXT NOT NULL,
                        correlation_id TEXT NOT NULL,
                        mission_id TEXT,
                        trace_id TEXT,
                        status TEXT NOT NULL CHECK
                            (status IN ('accepted', 'started', 'completed', 'failed')),
                        version INTEGER NOT NULL DEFAULT 0,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (tenant_id, idempotency_key),
                        UNIQUE (tenant_id, job_id)
                    )
                """)

    def _enqueue(self, conn, *, job: IngestionJob, event_id: str) -> None:
        message = AgentMessage(
            message_id=event_id,
            correlation_id=job.correlation_id,
            source="rkjo.multimodal",
            target="rkjo.multimodal.job_events",
            message_type="event",
            payload={
                "event": f"Job{job.status.value.capitalize()}",
                "job_id": job.job_id,
                "tenant_id": job.tenant_id,
                "status": job.status.value,
                "version": job.version,
            },
            metadata={
                "tenant_id": job.tenant_id,
                "mission_id": job.mission_id,
                "trace_id": job.trace_id,
                "channel": job.channel,
                "recipient_ref": job.recipient_ref,
                "idempotency_key": job.idempotency_key,
            },
        )
        PostgreSQLTransactionalOutboxStore(conn).add(
            OutboxMessage(outbox_id=event_id, queue_name=self.event_queue,
                          message=message, created_at=datetime.now(timezone.utc))
        )

    def accept_once(self, job: IngestionJob) -> IngestionJob:
        if job.status != JobStatus.ACCEPTED or job.version != 0:
            raise ValueError("New job must be accepted at version zero.")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO multimodal_ingestion_jobs (
                        job_id, tenant_id, idempotency_key, channel, recipient_ref,
                        correlation_id, mission_id, trace_id, status, version
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING
                    RETURNING job_id
                """, (job.job_id, job.tenant_id, job.idempotency_key,
                      job.channel, job.recipient_ref, job.correlation_id,
                      job.mission_id, job.trace_id, job.status.value, job.version))
                inserted = cur.fetchone()
                cur.execute(f"""
                    SELECT {_FIELDS} FROM multimodal_ingestion_jobs
                    WHERE tenant_id=%s AND idempotency_key=%s
                """, (job.tenant_id, job.idempotency_key))
                row = cur.fetchone()
                if row is None:
                    raise ValueError("Job identifier conflicts with an existing job.")
                existing = _job(row)
                if inserted:
                    self._enqueue(conn, job=existing, event_id=f"multimodal:{existing.job_id}:0")
                elif existing.job_id != job.job_id or replace(existing, status=job.status, version=job.version) != job:
                    raise ValueError("Idempotency key conflicts with another request.")
                return existing

    def load(self, *, tenant_id: str, job_id: str) -> IngestionJob | None:
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT {_FIELDS} FROM multimodal_ingestion_jobs
                    WHERE tenant_id=%s AND job_id=%s
                """, (tenant_id, job_id))
                row = cur.fetchone()
                return _job(row) if row else None

    def transition_and_enqueue_event(
        self, *, tenant_id: str, job_id: str, expected_version: int,
        new_status: JobStatus, event_id: str,
    ) -> IngestionJob:
        if not event_id.strip():
            raise ValueError("Event ID is required.")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT {_FIELDS} FROM multimodal_ingestion_jobs
                    WHERE tenant_id=%s AND job_id=%s FOR UPDATE
                """, (tenant_id, job_id))
                row = cur.fetchone()
                if row is None:
                    raise KeyError("Job not found for tenant.")
                current = _job(row)
                if current.version != expected_version:
                    raise ValueError("Stale job version.")
                updated = current.transition(new_status)
                cur.execute("""
                    UPDATE multimodal_ingestion_jobs
                    SET status=%s, version=%s, updated_at=CURRENT_TIMESTAMP
                    WHERE tenant_id=%s AND job_id=%s AND version=%s
                """, (updated.status.value, updated.version,
                      tenant_id, job_id, expected_version))
                if cur.rowcount != 1:
                    raise ValueError("Concurrent job update.")
                self._enqueue(conn, job=updated, event_id=event_id)
                return updated
