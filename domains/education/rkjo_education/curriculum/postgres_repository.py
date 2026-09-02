"""PostgreSQL curriculum repository."""

from __future__ import annotations

import json

import psycopg
from psycopg.types.json import Jsonb

from rkjo_education.curriculum.models import (
    Curriculum,
    CurriculumConcept,
    CurriculumTopic,
)


class PostgresCurriculumRepository:
    def __init__(
        self,
        database_url: str,
    ) -> None:
        if not database_url.strip():
            raise ValueError(
                "database_url must not be empty."
            )

        self.database_url = database_url
        self._ensure_schema()

    def _connect(self):
        return psycopg.connect(
            self.database_url
        )

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                education_curricula (
                    tenant_id TEXT NOT NULL,
                    curriculum_id TEXT NOT NULL,
                    country TEXT NOT NULL,
                    level TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    academic_year TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    topics JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL
                        DEFAULT NOW(),
                    PRIMARY KEY (
                        tenant_id,
                        curriculum_id
                    )
                )
                """
            )

    def save(
        self,
        curriculum: Curriculum,
    ) -> None:
        topics = [
            {
                "topic_id": topic.topic_id,
                "title": topic.title,
                "concepts": [
                    {
                        "concept_id":
                            concept.concept_id,
                        "title":
                            concept.title,
                    }
                    for concept
                    in topic.concepts
                ],
            }
            for topic
            in curriculum.topics
        ]

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO education_curricula (
                    tenant_id,
                    curriculum_id,
                    country,
                    level,
                    subject,
                    academic_year,
                    version,
                    topics
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                ON CONFLICT (
                    tenant_id,
                    curriculum_id
                )
                DO UPDATE SET
                    country = EXCLUDED.country,
                    level = EXCLUDED.level,
                    subject = EXCLUDED.subject,
                    academic_year =
                        EXCLUDED.academic_year,
                    version = EXCLUDED.version,
                    topics = EXCLUDED.topics,
                    updated_at = NOW()
                """,
                (
                    curriculum.tenant_id,
                    curriculum.curriculum_id,
                    curriculum.country,
                    curriculum.level,
                    curriculum.subject,
                    curriculum.academic_year,
                    curriculum.version,
                    Jsonb(topics),
                ),
            )

    def get(
        self,
        *,
        tenant_id: str,
        curriculum_id: str,
    ) -> Curriculum | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    country,
                    level,
                    subject,
                    academic_year,
                    version,
                    topics
                FROM education_curricula
                WHERE tenant_id = %s
                  AND curriculum_id = %s
                """,
                (
                    tenant_id.strip(),
                    curriculum_id.strip(),
                ),
            ).fetchone()

        if row is None:
            return None

        topics_data = row[5]

        if isinstance(topics_data, str):
            topics_data = json.loads(
                topics_data
            )

        topics = [
            CurriculumTopic(
                topic_id=topic[
                    "topic_id"
                ],
                title=topic[
                    "title"
                ],
                concepts=[
                    CurriculumConcept(
                        concept_id=concept[
                            "concept_id"
                        ],
                        title=concept[
                            "title"
                        ],
                    )
                    for concept
                    in topic[
                        "concepts"
                    ]
                ],
            )
            for topic
            in topics_data
        ]

        return Curriculum(
            curriculum_id=(
                curriculum_id.strip()
            ),
            tenant_id=tenant_id.strip(),
            country=row[0],
            level=row[1],
            subject=row[2],
            academic_year=row[3],
            version=int(row[4]),
            topics=topics,
        )
