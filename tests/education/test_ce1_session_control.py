import pytest

from rkjo_education.learning.ce1_orchestrator import TurnKind, new_session
from rkjo_education.learning.session_control import (
    ControlledCe1Session, SessionStatus, SessionUnavailable,
    StaleSessionVersion, TeacherCommand, apply_teacher_command, process_learner_turn,
)


def test_teacher_pause_blocks_all_learner_turns():
    controlled = ControlledCe1Session(new_session("learner"))
    paused = apply_teacher_command(controlled, TeacherCommand.PAUSE)
    assert paused.status == SessionStatus.PAUSED
    with pytest.raises(SessionUnavailable):
        process_learner_turn(paused, TurnKind.START, expected_version=paused.version)


def test_resume_and_stale_version_are_distinct():
    controlled = ControlledCe1Session(new_session("learner"))
    paused = apply_teacher_command(controlled, TeacherCommand.PAUSE)
    resumed = apply_teacher_command(paused, TeacherCommand.RESUME)
    with pytest.raises(StaleSessionVersion):
        process_learner_turn(resumed, TurnKind.START, expected_version=controlled.version)
    updated, result = process_learner_turn(resumed, TurnKind.START, expected_version=resumed.version)
    assert updated.version == resumed.version + 1
    assert result.session.lesson.phase.value == "check"


def test_teacher_commands_are_idempotent_and_end_is_terminal():
    session = ControlledCe1Session(new_session("learner"))
    paused = apply_teacher_command(session, TeacherCommand.PAUSE)
    assert apply_teacher_command(paused, TeacherCommand.PAUSE) == paused
    ended = apply_teacher_command(paused, TeacherCommand.END)
    assert apply_teacher_command(ended, TeacherCommand.END) == ended
    with pytest.raises(SessionUnavailable):
        apply_teacher_command(ended, TeacherCommand.RESUME)
    with pytest.raises(SessionUnavailable):
        process_learner_turn(ended, TurnKind.START, expected_version=ended.version)


def test_learner_turn_advances_version_to_fence_inflight_generation():
    session = ControlledCe1Session(new_session("learner"))
    changed, _ = process_learner_turn(session, TurnKind.START, expected_version=0)
    with pytest.raises(StaleSessionVersion):
        process_learner_turn(changed, TurnKind.START, expected_version=0)
