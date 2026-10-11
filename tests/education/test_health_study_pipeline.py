"""End-to-end contract tests, without LLM, database or PDF ingestion."""
from datetime import date
import pytest

from rkjo_education.curriculum.study_sources import (
    StudyDocumentType, StudySegment, StudySourcePackage
)
from rkjo_education.curriculum.study_artifacts import (
    StudyArtifact, StudyArtifactType, SourcedLearningItem
)
from rkjo_education.curriculum.health_study_generator import make_revision_outline
from rkjo_education.curriculum.health_model_router import route_health_tutor
from rkjo_education.learning.health_study_planner import starter_study_plan
from rkjo_education.learning.next_action_policy import LearningSignals


def course():
    s = StudySegment.from_text(
        document_id="cm-physio", page=3,
        text="Le débit cardiaque dépend de la fréquence cardiaque et du volume d'éjection."
    )
    return StudySourcePackage(
        tenant_id="universite-a", learner_id="student-42",
        programme_id="medicine-year-1", ue_id="physiologie",
        document_id="cm-physio", version=1, document_type=StudyDocumentType.CM,
        segments=(s,)
    )


def test_revision_outline_keeps_original_page_provenance():
    src = course()
    result = make_revision_outline(src)
    assert result.artifact_type == StudyArtifactType.REVISION_NOTE
    assert result.items[0].segment_ids == (src.segments[0].segment_id,)
    assert "débit cardiaque" in result.items[0].body


def test_reject_missing_citations_and_stale_versions():
    src = course()
    item = SourcedLearningItem("Question", "Réponse", ("unknown",))
    with pytest.raises(ValueError, match="Unverifiable"):
        StudyArtifact(StudyArtifactType.QUIZ, src.document_id, 1, (item,), "mock").validate_sources(src)
    with pytest.raises(ValueError, match="stale"):
        StudyArtifact(StudyArtifactType.QUIZ, src.document_id, 2, (item,), "mock").validate_sources(src)


def test_reject_generated_official_exam_claim():
    src = course()
    valid_item = SourcedLearningItem("QCM", "Exemple", (src.segments[0].segment_id,))
    with pytest.raises(ValueError, match="official"):
        StudyArtifact(StudyArtifactType.MOCK_EXAM, src.document_id, 1, (valid_item,),
                      "demo", is_official_exam=True).validate_sources(src)


@pytest.mark.parametrize("track", ["medicine", "pharmacy", "nursing"])
def test_model_routes_remain_nonclinical(track):
    route = route_health_tutor(track)
    assert route.model_profile.startswith("rkjo_")
    assert route.verified_sources_required
    assert not route.allow_patient_advice


def test_plan_has_dates_and_no_unverified_mastery():
    sessions = starter_study_plan(
        ue_id="physiologie", start=date(2026, 10, 11),
        exam=date(2026, 10, 15), minutes_per_day=45,
        signals=LearningSignals(assessed=False),
    )
    assert len(sessions) == 4
    assert sessions[0].activity == "diagnose"
    assert sessions[0].minutes == 45


def test_plan_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        starter_study_plan(
            ue_id="physiologie", start=date(2026, 10, 11),
            exam=date(2026, 10, 11), minutes_per_day=45,
            signals=LearningSignals(assessed=False),
        )
