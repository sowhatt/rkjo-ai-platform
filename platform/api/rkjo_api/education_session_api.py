"""Opt-in CE1 pilot session API: teacher pause and learner turn gate.

Fail-closed: requires a verified Bearer identity with UUID tenant/subject, and
explicit teacher->learner grants configured for the pilot. Never trusts API keys.
SQLite is a local multi-browser adapter, not production distributed storage.
"""
from __future__ import annotations

import json
import os
import sqlite3
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from rkjo_api.identity import get_authenticated_identity
from rkjo_api.security import ApiRole
from rkjo_education.learning.session_control import TeacherCommand
from rkjo_education.learning.sqlite_session_store import (
    SessionStoreConflict, SessionStoreDenied, SqliteSessionStateStore,
)

router = APIRouter(prefix="/education/ce1-sessions", tags=["education-pilot"])


class PilotGrant(BaseModel):
    tenant_id: UUID
    teacher_id: UUID
    learner_id: UUID


class CreateSessionBody(BaseModel):
    learner_id: UUID


class CommandBody(BaseModel):
    command: TeacherCommand
    expected_version: int = Field(ge=0)


class LearnerTurnBody(BaseModel):
    expected_version: int = Field(ge=0)


class PilotState(BaseModel):
    session_id: UUID
    status: str
    version: int


def _config() -> tuple[str, list[PilotGrant]]:
    if os.getenv("RKJO_EDU_CE1_PILOT_ENABLED") != "1":
        raise HTTPException(503, "CE1 pilot session API is disabled")
    db_path = os.getenv("RKJO_EDU_CE1_PILOT_DB", "").strip()
    grants_raw = os.getenv("RKJO_EDU_CE1_PILOT_GRANTS", "").strip()
    if not db_path or not grants_raw:
        raise HTTPException(503, "CE1 pilot storage/grants not configured")
    try:
        grants = [PilotGrant.model_validate(v) for v in json.loads(grants_raw)]
    except (ValueError, TypeError) as exc:
        raise HTTPException(503, "Invalid CE1 pilot grants") from exc
    return db_path, grants


def _actor(request: Request) -> tuple[UUID, UUID, ApiRole]:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(403, "Individual Bearer token required")
    identity = get_authenticated_identity(request)
    if not identity.subject or not identity.tenant_id:
        raise HTTPException(403, "Bound subject and tenant required")
    try:
        return UUID(identity.tenant_id), UUID(identity.subject), identity.role
    except ValueError as exc:
        raise HTTPException(403, "Subject and tenant must be UUIDs") from exc


def _grant(grants: list[PilotGrant], tenant: UUID, teacher: UUID, learner: UUID) -> None:
    if not any(g.tenant_id == tenant and g.teacher_id == teacher and g.learner_id == learner for g in grants):
        raise HTTPException(403, "No verified teacher-learner pilot grant")


def _connection(path: str) -> sqlite3.Connection:
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    db.execute("PRAGMA busy_timeout=10000")
    db.execute("""CREATE TABLE IF NOT EXISTS education_ce1_pilot_members (
        session_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
        teacher_id TEXT NOT NULL, learner_id TEXT NOT NULL,
        accepted_turns INTEGER NOT NULL DEFAULT 0
    )""")
    return db


def _membership(db: sqlite3.Connection, session_id: UUID) -> tuple[UUID, UUID, UUID]:
    row = db.execute(
        "SELECT tenant_id,teacher_id,learner_id FROM education_ce1_pilot_members WHERE session_id=?",
        (str(session_id),),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Session not found")
    return UUID(row[0]), UUID(row[1]), UUID(row[2])


@router.post("", response_model=PilotState, status_code=201)
def create_session(payload: CreateSessionBody, request: Request) -> PilotState:
    tenant, actor, role = _actor(request)
    path, grants = _config()
    if role not in (ApiRole.OPERATOR, ApiRole.ADMIN):
        raise HTTPException(403, "Teacher role required")
    _grant(grants, tenant, actor, payload.learner_id)
    store = SqliteSessionStateStore(path)
    store.initialize()
    session_id = uuid4()
    with _connection(path) as db:
        db.execute(
            "INSERT INTO education_ce1_pilot_members (session_id,tenant_id,teacher_id,learner_id) VALUES (?,?,?,?)",
            (str(session_id), str(tenant), str(actor), str(payload.learner_id)),
        )
    store.seed(session_id=session_id, tenant_id=tenant, teacher_id=actor)
    return PilotState(session_id=session_id, status="active", version=0)


@router.post("/{session_id}/commands", response_model=PilotState)
def teacher_command(session_id: UUID, payload: CommandBody, request: Request) -> PilotState:
    tenant, actor, role = _actor(request)
    path, grants = _config()
    if role not in (ApiRole.OPERATOR, ApiRole.ADMIN):
        raise HTTPException(403, "Teacher role required")
    with _connection(path) as db:
        st, teacher, learner = _membership(db, session_id)
    if tenant != st or actor != teacher:
        raise HTTPException(403, "Teacher not assigned to session")
    _grant(grants, tenant, actor, learner)
    store = SqliteSessionStateStore(path)
    try:
        state = store.command(
            session_id=session_id, tenant_id=tenant, teacher_id=actor,
            command=payload.command, expected_version=payload.expected_version,
        )
    except SessionStoreConflict as exc:
        raise HTTPException(409, "Stale session version") from exc
    except SessionStoreDenied as exc:
        raise HTTPException(403, "Command forbidden") from exc
    return PilotState(session_id=session_id, status=state.status.value, version=state.version)


@router.get("/{session_id}/state", response_model=PilotState)
def learner_state(session_id: UUID, request: Request) -> PilotState:
    tenant, actor, _ = _actor(request)
    path, grants = _config()
    with _connection(path) as db:
        st, teacher, learner = _membership(db, session_id)
    if tenant != st or actor != learner:
        raise HTTPException(403, "Learner not assigned to session")
    _grant(grants, tenant, teacher, learner)
    store = SqliteSessionStateStore(path)
    state = store.read(session_id=session_id, tenant_id=tenant, teacher_id=teacher)
    return PilotState(session_id=session_id, status=state.status.value, version=state.version)


@router.post("/{session_id}/turns", response_model=PilotState)
def learner_turn(session_id: UUID, payload: LearnerTurnBody, request: Request) -> PilotState:
    """Atomically reject activities during pause; does not grade an answer."""
    tenant, actor, _ = _actor(request)
    path, grants = _config()
    with _connection(path) as db:
        db.execute("BEGIN IMMEDIATE")
        st, teacher, learner = _membership(db, session_id)
        if tenant != st or actor != learner:
            raise HTTPException(403, "Learner not assigned to session")
        _grant(grants, tenant, teacher, learner)
        row = db.execute(
            "SELECT status,version FROM education_session_states WHERE session_id=?",
            (str(session_id),),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Session state unavailable")
        status, version = row
        if status != "active":
            raise HTTPException(423, "Teacher paused or ended the session")
        if version != payload.expected_version:
            raise HTTPException(409, "Stale session version")
        result = db.execute(
            """UPDATE education_session_states SET version=version+1
               WHERE session_id=? AND version=? AND status='active'""",
            (str(session_id), version),
        )
        if result.rowcount != 1:
            raise HTTPException(409, "Concurrent session transition")
        db.execute(
            "UPDATE education_ce1_pilot_members SET accepted_turns=accepted_turns+1 WHERE session_id=?",
            (str(session_id),),
        )
        db.execute("COMMIT")
    return PilotState(session_id=session_id, status="active", version=version + 1)


@router.get("/{session_id}/teacher-state", response_model=PilotState)
def teacher_state(session_id: UUID, request: Request) -> PilotState:
    """Teacher-only current state for optimistic command version selection."""
    tenant, actor, role = _actor(request)
    path, grants = _config()
    if role not in (ApiRole.OPERATOR, ApiRole.ADMIN):
        raise HTTPException(403, "Teacher role required")
    with _connection(path) as db:
        st, teacher, learner = _membership(db, session_id)
    if tenant != st or actor != teacher:
        raise HTTPException(403, "Teacher not assigned to session")
    _grant(grants, tenant, teacher, learner)
    store = SqliteSessionStateStore(path)
    state = store.read(session_id=session_id, tenant_id=tenant, teacher_id=actor)
    return PilotState(session_id=session_id, status=state.status.value, version=state.version)
