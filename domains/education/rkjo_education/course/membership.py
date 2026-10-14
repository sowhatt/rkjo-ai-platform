"""Tenant-scoped pedagogical course memberships.

Course-level roles are independent of API transport roles.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import psycopg


class CourseMemberRole(StrEnum):
    TEACHER = "teacher"
    LEARNER = "learner"


@dataclass(frozen=True)
class CourseMembership:
    tenant_id: str
    course_id: str
    subject: str
    role: CourseMemberRole


class PostgresCourseMembershipRepository:
    def __init__(self, database_url: str):
        if not database_url.strip():
            raise ValueError("database_url is required")
        self.database_url = database_url

    def initialize_schema(self):
        with psycopg.connect(self.database_url) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS education_course_memberships (
                    tenant_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('teacher', 'learner')),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (tenant_id, course_id, subject),
                    FOREIGN KEY (tenant_id, course_id)
                      REFERENCES education_courses(tenant_id, course_id)
                      ON DELETE CASCADE
                )
            """)

    def get(self, *, tenant_id: str, course_id: str, subject: str) -> CourseMembership | None:
        with psycopg.connect(self.database_url) as conn:
            row = conn.execute(
                """SELECT role FROM education_course_memberships
                   WHERE tenant_id=%s AND course_id=%s AND subject=%s""",
                (tenant_id, course_id, subject),
            ).fetchone()
        if row is None:
            return None
        return CourseMembership(tenant_id, course_id, subject, CourseMemberRole(row[0]))

    def upsert(self, member: CourseMembership) -> CourseMembership:
        with psycopg.connect(self.database_url) as conn:
            conn.execute(
                """INSERT INTO education_course_memberships
                   (tenant_id, course_id, subject, role)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (tenant_id,course_id,subject)
                   DO UPDATE SET role=EXCLUDED.role""",
                (member.tenant_id, member.course_id, member.subject, member.role.value),
            )
        return member


class CourseAccess:
    def __init__(self, repository):
        self.repository = repository

    def require(self, *, tenant_id: str, course_id: str, subject: str | None,
                allowed_roles: tuple[CourseMemberRole, ...]) -> CourseMembership:
        if not tenant_id or not tenant_id.strip() or not subject or not subject.strip():
            raise PermissionError("Subject and tenant are required")
        member = self.repository.get(
            tenant_id=tenant_id, course_id=course_id, subject=subject,
        )
        if member is None or member.role not in allowed_roles:
            raise PermissionError("Course membership required")
        return member
