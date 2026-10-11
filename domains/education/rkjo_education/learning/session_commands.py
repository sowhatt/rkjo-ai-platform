"""Authorized teacher command boundary for a CE1 session.

This module is a domain contract, NOT an HTTP endpoint or durable database.
Production adapters must verify JWT identity, tenant membership, and assignment
before constructing a TeacherContext, and commit state with optimistic locking.
"""
from dataclasses import dataclass
from uuid import UUID

from rkjo_education.learning.session_control import (
    ControlledCe1Session, TeacherCommand, apply_teacher_command,
)


class TeacherAccessDenied(PermissionError):
    pass


class SessionVersionConflict(ValueError):
    pass


@dataclass(frozen=True)
class TeacherContext:
    tenant_id: UUID
    teacher_id: UUID
    authenticated: bool
    can_control_session: bool


@dataclass(frozen=True)
class TeacherSessionRecord:
    tenant_id: UUID
    session_id: UUID
    teacher_id: UUID
    controlled: ControlledCe1Session


def issue_teacher_command(
    record: TeacherSessionRecord,
    actor: TeacherContext,
    command: TeacherCommand,
    *,
    expected_version: int,
) -> TeacherSessionRecord:
    """Check ownership and expected version before generating new state.

    No durable write happens here. A Postgres repository must use an atomic
    UPDATE ... WHERE version = expected_version and verify affected row count.
    """
    if (
        not actor.authenticated
        or not actor.can_control_session
        or actor.tenant_id != record.tenant_id
        or actor.teacher_id != record.teacher_id
    ):
        raise TeacherAccessDenied("Teacher is not authorized to control this session")
    if expected_version != record.controlled.version:
        raise SessionVersionConflict("Stale session version")
    return TeacherSessionRecord(
        tenant_id=record.tenant_id,
        session_id=record.session_id,
        teacher_id=record.teacher_id,
        controlled=apply_teacher_command(record.controlled, command),
    )
