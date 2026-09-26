from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from .models import LearnerSupervisionState


class SupervisionAlertCode(StrEnum):
    LOW_AUTONOMY = "low_autonomy"
    PROOF_FAILED = "proof_failed"
    ASSISTANCE_REPEATED = "assistance_repeated"


class SupervisionAlertSeverity(StrEnum):
    WARNING = "warning"
    CRITICAL = "critical"


class SupervisionAlert(BaseModel):
    code: SupervisionAlertCode
    severity: SupervisionAlertSeverity
    message: str


def alerts_for_state(state: LearnerSupervisionState) -> list[SupervisionAlert]:
    """Return deterministic pedagogical alerts for a learner snapshot."""
    alerts: list[SupervisionAlert] = []

    if state.autonomy_score is not None and state.autonomy_score < 40:
        alerts.append(SupervisionAlert(
            code=SupervisionAlertCode.LOW_AUTONOMY,
            severity=SupervisionAlertSeverity.WARNING,
            message="Autonomie faible : accompagnement pédagogique à envisager.",
        ))

    if state.proof_status == "failed":
        alerts.append(SupervisionAlert(
            code=SupervisionAlertCode.PROOF_FAILED,
            severity=SupervisionAlertSeverity.CRITICAL,
            message="Preuve d’apprentissage échouée : compétence à revoir.",
        ))

    if state.hints_requested >= 3 or state.tutor_requests >= 3:
        alerts.append(SupervisionAlert(
            code=SupervisionAlertCode.ASSISTANCE_REPEATED,
            severity=SupervisionAlertSeverity.WARNING,
            message="Assistance répétée : vérifier la compréhension de l’élève.",
        ))

    return alerts
