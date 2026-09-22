from __future__ import annotations

from uuid import UUID

import psycopg

from .proof import ProofStatus
from .proof_repository import StoredProofChallenge


class PostgresProofChallengeRepository:
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
                CREATE TABLE IF NOT EXISTS education_proof_challenges (
                    tenant_id UUID NOT NULL,
                    challenge_id UUID NOT NULL,
                    learner_id UUID NOT NULL,
                    course_id UUID NOT NULL,
                    competency_code TEXT NOT NULL,
                    source_question_id UUID NOT NULL,
                    verification_question_id UUID NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    completed_at TIMESTAMPTZ,
                    PRIMARY KEY (tenant_id, challenge_id),
                    CHECK (
                        source_question_id <>
                        verification_question_id
                    )
                )
                """
            )

    def save(
        self,
        challenge: StoredProofChallenge,
    ) -> StoredProofChallenge:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO education_proof_challenges (
                    tenant_id,
                    challenge_id,
                    learner_id,
                    course_id,
                    competency_code,
                    source_question_id,
                    verification_question_id,
                    status,
                    created_at,
                    completed_at
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                ON CONFLICT (tenant_id, challenge_id)
                DO UPDATE SET
                    status = EXCLUDED.status,
                    completed_at = EXCLUDED.completed_at
                """,
                (
                    challenge.tenant_id,
                    challenge.id,
                    challenge.learner_id,
                    challenge.course_id,
                    challenge.competency_code,
                    challenge.source_question_id,
                    challenge.verification_question_id,
                    challenge.status.value,
                    challenge.created_at,
                    challenge.completed_at,
                ),
            )

        return challenge

    def get(
        self,
        *,
        tenant_id: UUID,
        challenge_id: UUID,
    ) -> StoredProofChallenge | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    learner_id,
                    course_id,
                    competency_code,
                    source_question_id,
                    verification_question_id,
                    status,
                    created_at,
                    completed_at
                FROM education_proof_challenges
                WHERE tenant_id = %s
                  AND challenge_id = %s
                """,
                (tenant_id, challenge_id),
            ).fetchone()

        if row is None:
            return None

        return StoredProofChallenge(
            tenant_id=tenant_id,
            id=challenge_id,
            learner_id=row[0],
            course_id=row[1],
            competency_code=row[2],
            source_question_id=row[3],
            verification_question_id=row[4],
            status=ProofStatus(row[5]),
            created_at=row[6],
            completed_at=row[7],
        )
