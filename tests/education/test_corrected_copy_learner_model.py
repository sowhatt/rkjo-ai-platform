from datetime import datetime, timezone
from uuid import uuid4

from rkjo_education.events import EducationEventType, EducationLearningEvent
from rkjo_education.intelligence.learner_model import LearnerModelProjector


def test_corrected_copy_updates_mastery_and_retention_but_not_autonomy():
    now = datetime.now(timezone.utc)
    event = EducationLearningEvent(
        event_type=EducationEventType.CORRECTED_COPY_OBSERVED,
        tenant_id=uuid4(),
        learner_id=uuid4(),
        competency_code="MED.BIO.CELL",
        occurred_at=now,
        payload={
            "score": 0.5,
            "weight": 0.8,
            "source": "corrected_copy",
            "affects_autonomy": False,
        },
    )

    state = LearnerModelProjector().project(
        [event], competency_code="MED.BIO.CELL", now=now
    )

    assert state.mastery > 0.30
    assert state.mastery <= 0.75
    assert state.autonomy == 0.0
    assert state.retention == 1.0
    assert state.latest_correct is None
