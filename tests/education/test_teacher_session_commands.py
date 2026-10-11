from uuid import uuid4

import pytest

from rkjo_education.learning.ce1_orchestrator import new_session
from rkjo_education.learning.session_control import ControlledCe1Session, SessionStatus, TeacherCommand
from rkjo_education.learning.session_commands import (
    TeacherContext, TeacherSessionRecord, TeacherAccessDenied,
    SessionVersionConflict, issue_teacher_command,
)


def setup():
    tenant, teacher = uuid4(), uuid4()
    record = TeacherSessionRecord(
        tenant_id=tenant,
        session_id=uuid4(),
        teacher_id=teacher,
        controlled=ControlledCe1Session(new_session("student")),
    )
    return record, TeacherContext(tenant, teacher, True, True)


def test_owner_can_pause_and_resume_with_version_cas():
    record, actor = setup()
    paused = issue_teacher_command(record, actor, TeacherCommand.PAUSE, expected_version=0)
    assert paused.controlled.status == SessionStatus.PAUSED
    assert paused.controlled.version == 1
    with pytest.raises(SessionVersionConflict):
        issue_teacher_command(paused, actor, TeacherCommand.RESUME, expected_version=0)
    resumed = issue_teacher_command(paused, actor, TeacherCommand.RESUME, expected_version=1)
    assert resumed.controlled.status == SessionStatus.ACTIVE


@pytest.mark.parametrize("change", [
    {"authenticated": False},
    {"can_control_session": False},
    {"tenant_id": uuid4()},
    {"teacher_id": uuid4()},
])
def test_unauthorized_teacher_rejected(change):
    record, actor = setup()
    from dataclasses import replace
    with pytest.raises(TeacherAccessDenied):
        issue_teacher_command(record, replace(actor, **change), TeacherCommand.PAUSE, expected_version=0)


def test_no_change_when_repeated_pause():
    record, actor = setup()
    paused = issue_teacher_command(record, actor, TeacherCommand.PAUSE, expected_version=0)
    again = issue_teacher_command(paused, actor, TeacherCommand.PAUSE, expected_version=1)
    assert again == paused
