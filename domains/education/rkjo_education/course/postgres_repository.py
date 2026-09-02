"""PostgreSQL course repository."""

from __future__ import annotations

import json

import psycopg
from psycopg.types.json import Jsonb

from rkjo_education.course.models import (
    Course,
)


class PostgresCourseRepository:
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
                education_courses (
                    tenant_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    level TEXT NOT NULL,
                    curriculum_id TEXT,
                    document_ids JSONB NOT NULL
                        DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL
                        DEFAULT NOW(),
                    PRIMARY KEY (
                        tenant_id,
                        course_id
                    )
                )
                """
            )

    def save(
        self,
        course: Course,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO education_courses (
                    tenant_id,
                    course_id,
                    title,
                    subject,
                    level,
                    curriculum_id,
                    document_ids
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
                ON CONFLICT (
                    tenant_id,
                    course_id
                )
                DO UPDATE SET
                    title = EXCLUDED.title,
                    subject = EXCLUDED.subject,
                    level = EXCLUDED.level,
                    curriculum_id =
                        EXCLUDED.curriculum_id,
                    document_ids =
                        EXCLUDED.document_ids,
                    updated_at = NOW()
                """,
                (
                    course.tenant_id,
                    course.course_id,
                    course.title,
                    course.subject,
                    course.level,
                    course.curriculum_id,
                    Jsonb(
                        course.document_ids
                    ),
                ),
            )

    def get(
        self,
        *,
        tenant_id: str,
        course_id: str,
    ) -> Course | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    title,
                    subject,
                    level,
                    curriculum_id,
                    document_ids
                FROM education_courses
                WHERE tenant_id = %s
                  AND course_id = %s
                """,
                (
                    tenant_id.strip(),
                    course_id.strip(),
                ),
            ).fetchone()

        if row is None:
            return None

        document_ids = row[4]

        if isinstance(document_ids, str):
            document_ids = json.loads(
                document_ids
            )

        return Course(
            course_id=course_id.strip(),
            tenant_id=tenant_id.strip(),
            title=row[0],
            subject=row[1],
            level=row[2],
            curriculum_id=row[3],
            document_ids=list(
                document_ids
            ),
        )


def _row_to_course(
    *,
    tenant_id: str,
    row,
) -> Course:
    document_ids = row[5]

    if isinstance(
        document_ids,
        str,
    ):
        document_ids = json.loads(
            document_ids
        )

    return Course(
        course_id=row[0],
        tenant_id=tenant_id,
        title=row[1],
        subject=row[2],
        level=row[3],
        curriculum_id=row[4],
        document_ids=list(
            document_ids
        ),
    )


def _list_for_tenant(
    self,
    tenant_id: str,
) -> list[Course]:
    normalized_tenant_id = (
        tenant_id.strip()
    )

    with self._connect() as connection:
        rows = connection.execute(
            """
            SELECT
                course_id,
                title,
                subject,
                level,
                curriculum_id,
                document_ids
            FROM education_courses
            WHERE tenant_id = %s
            ORDER BY title, course_id
            """,
            (
                normalized_tenant_id,
            ),
        ).fetchall()

    return [
        _row_to_course(
            tenant_id=normalized_tenant_id,
            row=row,
        )
        for row in rows
    ]


PostgresCourseRepository.list_for_tenant = (
    _list_for_tenant
)
