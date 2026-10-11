from uuid import uuid4

import pytest

from rkjo_education.supervision.safety_alerts import (
    SafetyAlert, SafetyAlertKind, dispatch_safety_alert,
)


class FakeTeacherAlertSink:
    def __init__(self):
        self.alerts = []

    def publish(self, alert):
        self.alerts.append(alert)


def test_safety_alert_reaches_teacher_without_learning_proof_write():
    sink = FakeTeacherAlertSink()
    alert = SafetyAlert(
        alert_id=uuid4(), tenant_id=uuid4(), session_id=uuid4(),
        learner_id=uuid4(), kind=SafetyAlertKind.UNSAFE_CONTENT,
    )
    dispatch_safety_alert(alert, sink)
    assert sink.alerts == [alert]
    assert alert.requires_teacher_attention


def test_safety_alert_has_no_raw_child_content_fields():
    fields = set(SafetyAlert.__dataclass_fields__)
    assert not fields.intersection({"raw_message", "prompt", "student_name", "transcript"})


def test_unknown_alert_kind_is_rejected():
    sink = FakeTeacherAlertSink()
    alert = SafetyAlert(uuid4(), uuid4(), uuid4(), uuid4(), "unsupported")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        dispatch_safety_alert(alert, sink)
    assert sink.alerts == []
