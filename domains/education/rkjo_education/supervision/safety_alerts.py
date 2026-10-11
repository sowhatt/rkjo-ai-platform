"""Immediate safety alert contract; independent of learning-proof persistence.

No child content, full prompt or personally identifying data in the alert.
Delivery is a separate production responsibility (durable queue / SSE).
"""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol
from uuid import UUID


class SafetyAlertKind(str, Enum):
    UNSAFE_CONTENT = "unsafe_content"
    SELF_HARM_CONCERN = "self_harm_concern"
    SUSPICIOUS_CONTACT = "suspicious_contact"
    CONTENT_FILTER_ERROR = "content_filter_error"


@dataclass(frozen=True)
class SafetyAlert:
    alert_id: UUID
    tenant_id: UUID
    session_id: UUID
    learner_id: UUID
    kind: SafetyAlertKind
    requires_teacher_attention: bool = True


class TeacherAlertSink(Protocol):
    def publish(self, alert: SafetyAlert) -> None: ...


class DuplicateAlert(ValueError):
    pass


def dispatch_safety_alert(alert: SafetyAlert, sink: TeacherAlertSink) -> None:
    """S -> T directly. Do not route through proof/mastery persistence."""
    if not isinstance(alert.kind, SafetyAlertKind):
        raise ValueError("Unsupported safety alert kind")
    sink.publish(alert)
