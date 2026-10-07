"""Durable learner-owned document and alignment repository."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from .models import EducationDocument


@dataclass(frozen=True, slots=True)
class StoredQuestionAlignment:
    question_ref: str
    competency_code: str | None
    alignment_confidence: float
    requires_confirmation: bool
    earned_points: float | None
    max_points: float | None
    confirmed: bool = False


class PostgresEducationDocumentRepository:
    def __init__(self, database_url: str) -> None:
        if not database_url.strip():
            raise ValueError("database_url must not be empty.")
        self.database_url = database_url
        self._ensure_schema()

    def _connect(self):
        return psycopg.connect(self.database_url)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS education_learner_documents (
                    tenant_id UUID NOT NULL,
                    document_id UUID NOT NULL,
                    learner_id UUID NOT NULL,
                    filename TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    extracted_text TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    question_alignments JSONB NOT NULL DEFAULT '[]'::jsonb,
                    learning_applied BOOLEAN NOT NULL DEFAULT FALSE,
                    PRIMARY KEY (tenant_id, document_id)
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_education_documents_learner
                ON education_learner_documents (tenant_id, learner_id)
            """)

    def save(
        self,
        document: EducationDocument,
        alignments: list[StoredQuestionAlignment],
    ) -> EducationDocument:
        with self._connect() as connection:
            connection.execute("""
                INSERT INTO education_learner_documents (
                    tenant_id, document_id, learner_id, filename, media_type,
                    kind, provenance, extracted_text, source_hash, question_alignments
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (tenant_id, document_id) DO UPDATE SET
                    question_alignments = EXCLUDED.question_alignments
            """, (
                document.tenant_id, document.id, document.learner_id,
                document.filename, document.media_type, document.kind.value,
                document.provenance.value, document.extracted_text,
                document.source_hash,
                Jsonb([{
                    "question_ref": a.question_ref,
                    "competency_code": a.competency_code,
                    "alignment_confidence": a.alignment_confidence,
                    "requires_confirmation": a.requires_confirmation,
                    "earned_points": a.earned_points,
                    "max_points": a.max_points,
                    "confirmed": a.confirmed,
                } for a in alignments]),
            ))
        return document

    def confirm_alignment(
        self, *, tenant_id: UUID, learner_id: UUID, document_id: UUID,
        question_ref: str, competency_code: str,
    ) -> StoredQuestionAlignment | None:
        with self._connect() as connection:
            row = connection.execute("""
                SELECT question_alignments FROM education_learner_documents
                WHERE tenant_id=%s AND learner_id=%s AND document_id=%s
            """, (tenant_id, learner_id, document_id)).fetchone()
            if row is None:
                return None
            items = list(row[0])
            selected = None
            for item in items:
                if item["question_ref"] == question_ref:
                    item["competency_code"] = competency_code
                    item["alignment_confidence"] = 1.0
                    item["requires_confirmation"] = False
                    item["confirmed"] = True
                    selected = item
                    break
            if selected is None:
                return None
            connection.execute("""
                UPDATE education_learner_documents SET question_alignments=%s
                WHERE tenant_id=%s AND learner_id=%s AND document_id=%s
            """, (Jsonb(items), tenant_id, learner_id, document_id))
        return StoredQuestionAlignment(**selected)


    def get_alignments(
        self, *, tenant_id: UUID, learner_id: UUID, document_id: UUID,
    ) -> list[StoredQuestionAlignment] | None:
        with self._connect() as connection:
            row = connection.execute("""
                SELECT question_alignments FROM education_learner_documents
                WHERE tenant_id=%s AND learner_id=%s AND document_id=%s
            """, (tenant_id, learner_id, document_id)).fetchone()
        if row is None:
            return None
        return [StoredQuestionAlignment(**item) for item in row[0]]

    def mark_learning_applied(
        self, *, tenant_id: UUID, learner_id: UUID, document_id: UUID,
    ) -> bool:
        with self._connect() as connection:
            row = connection.execute("""
                UPDATE education_learner_documents
                SET learning_applied=TRUE
                WHERE tenant_id=%s AND learner_id=%s AND document_id=%s
                  AND learning_applied=FALSE
                RETURNING document_id
            """, (tenant_id, learner_id, document_id)).fetchone()
        return row is not None
