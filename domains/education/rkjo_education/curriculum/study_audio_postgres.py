"""Pilot-only transactional PostgreSQL audio staging.

The audio is kept as BYTEA so the file and its metadata commit atomically.
For production, replace this with encrypted object storage + durable outbox.
No background processing or payment is triggered here.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import uuid4

import psycopg

from rkjo_education.curriculum.study_audio_probe import AudioProbe

RETENTION_HOURS = 24


class StagedAudioNotFound(KeyError):
    pass


class PostgresStudyAudioStaging:
    def __init__(self, database_url: str):
        if not database_url:
            raise ValueError("database_url is required")
        self.database_url = database_url

    def initialize_schema(self) -> None:
        with psycopg.connect(self.database_url) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS education_staged_audio (
                    source_id UUID PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    learner_id TEXT NOT NULL,
                    programme_id TEXT NOT NULL,
                    ue_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    sha256 CHAR(64) NOT NULL,
                    size_bytes BIGINT NOT NULL,
                    duration_ms BIGINT NOT NULL,
                    sample_rate INTEGER NOT NULL,
                    channels INTEGER NOT NULL,
                    audio_data BYTEA NOT NULL,
                    state TEXT NOT NULL DEFAULT 'staged',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    expires_at TIMESTAMPTZ NOT NULL,
                    UNIQUE (tenant_id, learner_id, programme_id, ue_id, sha256)
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_education_staged_audio_owner
                ON education_staged_audio (tenant_id, learner_id, created_at DESC);
            """)

    def stage(
        self, *, tenant_id: str, learner_id: str, programme_id: str,
        ue_id: str, filename: str, data: bytes, probe: AudioProbe,
    ) -> dict[str, object]:
        if not all((tenant_id, learner_id, programme_id, ue_id, filename)):
            raise ValueError("Missing audio ownership or source metadata")
        if len(data) != probe.size_bytes:
            raise ValueError("Audio length mismatch")
        source_id = str(uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(hours=RETENTION_HOURS)
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cursor:
                # Permit restaging after the 24h expiry without retaining stale bytes.
                cursor.execute("""
                    DELETE FROM education_staged_audio
                    WHERE tenant_id=%s AND learner_id=%s AND programme_id=%s
                      AND ue_id=%s AND sha256=%s AND expires_at <= now()
                """, (tenant_id, learner_id, programme_id, ue_id, probe.sha256))
                cursor.execute("""
                    INSERT INTO education_staged_audio (
                        source_id, tenant_id, learner_id, programme_id, ue_id,
                        filename, sha256, size_bytes, duration_ms, sample_rate,
                        channels, audio_data, expires_at
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) ON CONFLICT (tenant_id, learner_id, programme_id, ue_id, sha256)
                      DO NOTHING
                    RETURNING source_id
                """, (
                    source_id, tenant_id, learner_id, programme_id, ue_id,
                    filename, probe.sha256, probe.size_bytes, probe.duration_ms,
                    probe.sample_rate, probe.channels, data, expires_at,
                ))
                inserted = cursor.fetchone()
                if inserted:
                    actual_id = str(inserted[0])
                else:
                    cursor.execute("""
                        SELECT source_id FROM education_staged_audio
                        WHERE tenant_id=%s AND learner_id=%s
                          AND programme_id=%s AND ue_id=%s AND sha256=%s
                    """, (tenant_id, learner_id, programme_id, ue_id, probe.sha256))
                    row = cursor.fetchone()
                    if not row:
                        raise RuntimeError("Concurrent audio stage not found")
                    actual_id = str(row[0])
        return self.get(tenant_id=tenant_id, learner_id=learner_id, source_id=actual_id)

    def get(self, *, tenant_id: str, learner_id: str, source_id: str) -> dict[str, object]:
        try:
            with psycopg.connect(self.database_url) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT source_id, programme_id, ue_id, filename,
                               sha256, size_bytes, duration_ms, sample_rate,
                               channels, state, expires_at
                        FROM education_staged_audio
                        WHERE source_id=%s::uuid AND tenant_id=%s AND learner_id=%s
                          AND expires_at > now()
                    """, (source_id, tenant_id, learner_id))
                    row = cursor.fetchone()
        except psycopg.errors.InvalidTextRepresentation as exc:
            raise StagedAudioNotFound(source_id) from exc
        if row is None:
            raise StagedAudioNotFound(source_id)
        keys = ("source_id", "programme_id", "ue_id", "filename", "sha256",
                "size_bytes", "duration_ms", "sample_rate", "channels",
                "state", "expires_at")
        result = dict(zip(keys, row))
        result["source_id"] = str(result["source_id"])
        result["expires_at"] = result["expires_at"].isoformat()
        result["transcription_started"] = False
        result["payment_started"] = False
        return result

    def delete(self, *, tenant_id: str, learner_id: str, source_id: str) -> bool:
        try:
            with psycopg.connect(self.database_url) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        DELETE FROM education_staged_audio
                        WHERE source_id=%s::uuid AND tenant_id=%s AND learner_id=%s
                    """, (source_id, tenant_id, learner_id))
                    return cursor.rowcount > 0
        except psycopg.errors.InvalidTextRepresentation:
            return False

    def purge_expired(self) -> int:
        """Must be called by a scheduled maintenance task; never implicit."""
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM education_staged_audio WHERE expires_at <= now()")
                return cursor.rowcount
