"""Provider-neutral study material generation tests; no live LLM required."""
import pytest

from rkjo_education.curriculum.health_artifact_pipeline import (
    StudyGenerationError, generate_study_artifact,
)
from rkjo_education.curriculum.study_artifacts import StudyArtifactType
from rkjo_education.curriculum.study_sources import (
    StudyDocumentType, StudySegment, StudySourcePackage,
)


def source():
    segment = StudySegment.from_text(
        document_id="cm1", page=2, text="Le coeur comprend quatre cavites."
    )
    return StudySourcePackage(
        tenant_id="univ-a", learner_id="learner-1", programme_id="medicine-1",
        ue_id="anatomy", document_id="cm1", version=1,
        document_type=StudyDocumentType.CM, segments=(segment,),
    )


class MockProvider:
    def __init__(self, output):
        self.output = output
        self.last_request = None

    def generate(self, request):
        self.last_request = request
        return self.output


@pytest.mark.parametrize("kind", list(StudyArtifactType))
@pytest.mark.parametrize("track", ["medicine", "pharmacy", "nursing"])
def test_generated_items_are_sourced_and_routed(kind, track):
    src = source()
    model = MockProvider({"items": [{
        "title": "Question de cours", "body": "Quatre cavites selon le CM.",
        "segment_ids": [src.segments[0].segment_id],
    }]})
    result = generate_study_artifact(
        source=src, track=track, artifact_type=kind, provider=model
    )
    assert result.artifact_type == kind
    assert model.last_request.model_profile.startswith("rkjo_")
    assert model.last_request.ue_id == "anatomy"
    assert result.items[0].segment_ids == (src.segments[0].segment_id,)
    assert result.is_official_exam is False


@pytest.mark.parametrize("invalid", [
    {"items": []},
    {"items": [{"title": "No refs", "body": "Body", "segment_ids": []}]},
    {"items": [{"title": "Bad ref", "body": "Body", "segment_ids": ["fabricated"]}]},
    {"items": [{"title": "Bad type", "body": 123, "segment_ids": ["any"]}]},
])
def test_rejects_invalid_or_fabricated_citations(invalid):
    with pytest.raises((StudyGenerationError, ValueError)):
        generate_study_artifact(
            source=source(), track="medicine",
            artifact_type=StudyArtifactType.QUIZ,
            provider=MockProvider(invalid),
        )


def test_provider_must_return_object():
    with pytest.raises(StudyGenerationError):
        generate_study_artifact(
            source=source(), track="nursing",
            artifact_type=StudyArtifactType.REVISION_NOTE,
            provider=MockProvider("unstructured response"),
        )
