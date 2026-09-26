from uuid import uuid4

from rkjo_education.supervision.alerts import (
    SupervisionAlertCode,
    SupervisionAlertSeverity,
    alerts_for_state,
)
from rkjo_education.supervision.models import LearnerSupervisionState


def state(**kwargs):
    values = {
        "tenant_id": uuid4(),
        "learner_id": uuid4(),
    }
    values.update(kwargs)
    return LearnerSupervisionState(**values)


def test_low_autonomy_is_deterministic_warning():
    alerts = alerts_for_state(state(autonomy_score=25, mastery="developing"))
    assert [(item.code, item.severity) for item in alerts] == [
        (SupervisionAlertCode.LOW_AUTONOMY, SupervisionAlertSeverity.WARNING)
    ]


def test_failed_proof_is_critical():
    alerts = alerts_for_state(state(proof_status="failed"))
    assert alerts[0].code == SupervisionAlertCode.PROOF_FAILED
    assert alerts[0].severity == SupervisionAlertSeverity.CRITICAL


def test_repeated_assistance_is_flagged():
    alerts = alerts_for_state(state(hints_requested=3))
    assert alerts[0].code == SupervisionAlertCode.ASSISTANCE_REPEATED


def test_healthy_state_has_no_alert():
    alerts = alerts_for_state(state(
        autonomy_score=82,
        mastery="mastered",
        proof_status="passed",
        hints_requested=1,
        tutor_requests=0,
    ))
    assert alerts == []
