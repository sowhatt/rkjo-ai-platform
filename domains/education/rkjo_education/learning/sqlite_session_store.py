"""Development SQLite session-state adapter with atomic optimistic locking.

Does not store child responses. Not a production PostgreSQL adapter, HTTP API,
authentication provider, or teacher-grant registry.
"""
import sqlite3
from dataclasses import dataclass
from uuid import UUID

from rkjo_education.learning.session_control import SessionStatus, TeacherCommand


class SessionStoreConflict(ValueError):
    pass


class SessionStoreDenied(PermissionError):
    pass


@dataclass(frozen=True)
class StoredSessionState:
    session_id: UUID
    tenant_id: UUID
    teacher_id: UUID
    status: SessionStatus
    version: int


class SqliteSessionStateStore:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def initialize(self) -> None:
        with sqlite3.connect(self.db_path, timeout=10) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS education_session_states (
                session_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
                teacher_id TEXT NOT NULL, status TEXT NOT NULL,
                version INTEGER NOT NULL CHECK (version >= 0)
            )""")

    def seed(self, *, session_id: UUID, tenant_id: UUID, teacher_id: UUID) -> None:
        """Test/dev provisioning only; production must verify enrollment and grants."""
        with sqlite3.connect(self.db_path, timeout=10) as db:
            db.execute(
                """INSERT INTO education_session_states
                   (session_id,tenant_id,teacher_id,status,version)
                   VALUES (?,?,?,?,0)""",
                (str(session_id), str(tenant_id), str(teacher_id), SessionStatus.ACTIVE.value),
            )

    def command(self, *, session_id: UUID, tenant_id: UUID, teacher_id: UUID,
                command: TeacherCommand, expected_version: int) -> StoredSessionState:
        """One DB transaction fences stale/parallel commands and enforces assignment."""
        with sqlite3.connect(self.db_path, timeout=10, isolation_level=None) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT tenant_id, teacher_id, status, version
                   FROM education_session_states WHERE session_id=?""",
                (str(session_id),),
            ).fetchone()
            if row is None:
                raise SessionStoreDenied("Unknown session")
            stored_tenant, stored_teacher, status_text, version = row
            if stored_tenant != str(tenant_id) or stored_teacher != str(teacher_id):
                raise SessionStoreDenied("Session assignment mismatch")
            if version != expected_version:
                raise SessionStoreConflict("Session state changed")
            status = SessionStatus(status_text)
            if status == SessionStatus.ENDED and command != TeacherCommand.END:
                raise SessionStoreDenied("Ended session is terminal")
            target = {
                TeacherCommand.PAUSE: SessionStatus.PAUSED,
                TeacherCommand.RESUME: SessionStatus.ACTIVE,
                TeacherCommand.END: SessionStatus.ENDED,
            }[command]
            if status == SessionStatus.ENDED:
                target = SessionStatus.ENDED
            if status != target:
                updated = db.execute(
                    """UPDATE education_session_states SET status=?, version=version+1
                       WHERE session_id=? AND version=?""",
                    (target.value, str(session_id), expected_version),
                )
                if updated.rowcount != 1:
                    raise SessionStoreConflict("Concurrent session update")
                version += 1
            db.execute("COMMIT")
            return StoredSessionState(session_id, tenant_id, teacher_id, target, version)

    def read(self, *, session_id: UUID, tenant_id: UUID, teacher_id: UUID) -> StoredSessionState:
        with sqlite3.connect(self.db_path, timeout=10) as db:
            row = db.execute(
                """SELECT tenant_id,teacher_id,status,version FROM education_session_states
                   WHERE session_id=?""",
                (str(session_id),),
            ).fetchone()
        if row is None or row[0] != str(tenant_id) or row[1] != str(teacher_id):
            raise SessionStoreDenied("Session not accessible")
        return StoredSessionState(session_id, tenant_id, teacher_id, SessionStatus(row[2]), row[3])
