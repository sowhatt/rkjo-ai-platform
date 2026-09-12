"""Repositories for Meeting Intelligence transcription jobs."""

from __future__ import annotations

import psycopg

from rkjo_meeting_intelligence.application.transcription import TranscriptionJob, TranscriptionStatus


class InMemoryTranscriptionRepository:
    def __init__(self) -> None:
        self._jobs: dict[tuple[str, str, str], TranscriptionJob] = {}

    def save(self, job: TranscriptionJob) -> TranscriptionJob:
        self._jobs[(job.tenant_id, job.meeting_id, job.job_id)] = job
        return job

    def get(self, *, tenant_id: str, meeting_id: str, job_id: str) -> TranscriptionJob | None:
        return self._jobs.get((tenant_id.strip(), meeting_id.strip(), job_id.strip()))


class PostgresTranscriptionRepository:
    def __init__(self, database_url: str) -> None:
        if not database_url.strip():
            raise ValueError("database_url must not be empty.")
        self.database_url = database_url
        self._ensure_schema()

    def _connect(self):
        return psycopg.connect(self.database_url)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS meeting_intelligence_transcription_jobs (
                    tenant_id TEXT NOT NULL,
                    meeting_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (tenant_id, meeting_id, job_id)
                )
                """
            )

    def save(self, job: TranscriptionJob) -> TranscriptionJob:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO meeting_intelligence_transcription_jobs
                    (tenant_id, meeting_id, job_id, asset_id, status, error, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, meeting_id, job_id)
                DO UPDATE SET asset_id = EXCLUDED.asset_id,
                              status = EXCLUDED.status,
                              error = EXCLUDED.error,
                              updated_at = EXCLUDED.updated_at
                """,
                (job.tenant_id, job.meeting_id, job.job_id, job.asset_id,
                 job.status.value, job.error, job.created_at, job.updated_at),
            )
        return job

    def get(self, *, tenant_id: str, meeting_id: str, job_id: str) -> TranscriptionJob | None:
        tenant_id = tenant_id.strip(); meeting_id = meeting_id.strip(); job_id = job_id.strip()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT asset_id, status, error, created_at, updated_at
                FROM meeting_intelligence_transcription_jobs
                WHERE tenant_id = %s AND meeting_id = %s AND job_id = %s
                """,
                (tenant_id, meeting_id, job_id),
            ).fetchone()
        if row is None:
            return None
        return TranscriptionJob(
            job_id=job_id, tenant_id=tenant_id, meeting_id=meeting_id,
            asset_id=row[0], status=TranscriptionStatus(row[1]), error=row[2],
            created_at=row[3], updated_at=row[4],
        )
