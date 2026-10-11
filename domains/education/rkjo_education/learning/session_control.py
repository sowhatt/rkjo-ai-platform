"""Teacher commands and pause fence for the CE1 Learning Engine.

Pure domain contract. Production API must authorize commands and persist the
state atomically before making it visible to concurrent workers.
"""
from dataclasses import dataclass, replace
from enum import Enum

from rkjo_education.learning.ce1_orchestrator import Ce1LearningSession, Ce1TurnResult, TurnKind, transition


class SessionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class TeacherCommand(str, Enum):
    PAUSE = "pause"
    RESUME = "resume"
    END = "end"


class SessionUnavailable(ValueError):
    """Activity is forbidden because the teacher paused or ended the session."""


class StaleSessionVersion(ValueError):
    """A model response was produced against an obsolete session version."""


@dataclass(frozen=True)
class ControlledCe1Session:
    session: Ce1LearningSession
    status: SessionStatus = SessionStatus.ACTIVE
    version: int = 0


def apply_teacher_command(
    controlled: ControlledCe1Session,
    command: TeacherCommand,
) -> ControlledCe1Session:
    if controlled.status == SessionStatus.ENDED:
        if command == TeacherCommand.END:
            return controlled
        raise SessionUnavailable("Ended sessions cannot be resumed")

    if command == TeacherCommand.PAUSE:
        if controlled.status == SessionStatus.PAUSED:
            return controlled
        return replace(controlled, status=SessionStatus.PAUSED, version=controlled.version + 1)
    if command == TeacherCommand.RESUME:
        if controlled.status == SessionStatus.ACTIVE:
            return controlled
        return replace(controlled, status=SessionStatus.ACTIVE, version=controlled.version + 1)
    if command == TeacherCommand.END:
        return replace(controlled, status=SessionStatus.ENDED, version=controlled.version + 1)
    raise ValueError("Unsupported teacher command")


def process_learner_turn(
    controlled: ControlledCe1Session,
    turn: TurnKind,
    *,
    answer: int | None = None,
    expected_version: int,
) -> tuple[ControlledCe1Session, Ce1TurnResult]:
    """Fence stale generations and reject new work on a paused session.

    The durable adapter MUST repeat the version check in a transactional update;
    this pure check alone does not make a multi-worker deployment race-free.
    """
    if controlled.version != expected_version:
        raise StaleSessionVersion("Session changed while the activity was in progress")
    if controlled.status != SessionStatus.ACTIVE:
        raise SessionUnavailable("Session is not active")
    result = transition(controlled.session, turn, answer)
    return replace(controlled, session=result.session, version=controlled.version + 1), result
