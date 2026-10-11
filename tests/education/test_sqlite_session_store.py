from uuid import uuid4
import pytest

from rkjo_education.learning.sqlite_session_store import (
    SqliteSessionStateStore, SessionStoreConflict, SessionStoreDenied,
)
from rkjo_education.learning.session_control import SessionStatus, TeacherCommand


def prepared(tmp_path):
    path = str(tmp_path / "sessions.db")
    store = SqliteSessionStateStore(path)
    store.initialize()
    session, tenant, teacher = uuid4(), uuid4(), uuid4()
    store.seed(session_id=session, tenant_id=tenant, teacher_id=teacher)
    return store, path, session, tenant, teacher


def test_pause_persists_after_new_store_instance(tmp_path):
    store, path, session, tenant, teacher = prepared(tmp_path)
    state = store.command(session_id=session, tenant_id=tenant, teacher_id=teacher,
                          command=TeacherCommand.PAUSE, expected_version=0)
    reopened = SqliteSessionStateStore(path)
    assert reopened.read(session_id=session, tenant_id=tenant, teacher_id=teacher) == state
    assert state.status == SessionStatus.PAUSED


def test_stale_command_refused(tmp_path):
    store, _, session, tenant, teacher = prepared(tmp_path)
    store.command(session_id=session, tenant_id=tenant, teacher_id=teacher,
                  command=TeacherCommand.PAUSE, expected_version=0)
    with pytest.raises(SessionStoreConflict):
        store.command(session_id=session, tenant_id=tenant, teacher_id=teacher,
                      command=TeacherCommand.RESUME, expected_version=0)


def test_repeat_pause_idempotent(tmp_path):
    store, _, session, tenant, teacher = prepared(tmp_path)
    params = dict(session_id=session, tenant_id=tenant, teacher_id=teacher)
    first = store.command(**params, command=TeacherCommand.PAUSE, expected_version=0)
    same = store.command(**params, command=TeacherCommand.PAUSE, expected_version=1)
    assert first == same


def test_cross_tenant_and_unassigned_teacher_denied(tmp_path):
    store, _, session, tenant, teacher = prepared(tmp_path)
    with pytest.raises(SessionStoreDenied):
        store.command(session_id=session, tenant_id=uuid4(), teacher_id=teacher,
                      command=TeacherCommand.PAUSE, expected_version=0)
    with pytest.raises(SessionStoreDenied):
        store.read(session_id=session, tenant_id=tenant, teacher_id=uuid4())


def test_end_is_terminal(tmp_path):
    store, _, session, tenant, teacher = prepared(tmp_path)
    args = dict(session_id=session, tenant_id=tenant, teacher_id=teacher)
    ended = store.command(**args, command=TeacherCommand.END, expected_version=0)
    assert ended.status == SessionStatus.ENDED
    with pytest.raises(SessionStoreDenied):
        store.command(**args, command=TeacherCommand.RESUME, expected_version=1)
