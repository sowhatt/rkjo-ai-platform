"""Regression checks for existing provider-neutral structured artifact generation."""
import pytest
from rkjo_education.curriculum.health_artifact_pipeline import generate_study_artifact
from rkjo_education.curriculum.study_artifacts import StudyArtifactType
from rkjo_education.curriculum.study_sources import StudyDocumentType, StudySegment, StudySourcePackage

def source():
    segment = StudySegment.from_text(document_id="course", page=4, text="Cours fictif de physiologie.")
    return StudySourcePackage(tenant_id="t", learner_id="l", programme_id="p",
        ue_id="physiologie", document_id="course", version=1,
        document_type=StudyDocumentType.CM, segments=(segment,))

class Provider:
    def __init__(self, bad=False):
        self.bad = bad
    def generate(self, request):
        ref = "missing-id" if self.bad else request.source_segments[0][0]
        return {"items": [{"title": "Révision expérimentale", "body": "A vérifier avec le cours.", "segment_ids": [ref]}]}

@pytest.mark.parametrize("kind", [StudyArtifactType.REVISION_NOTE, StudyArtifactType.MIND_MAP])
def test_generated_artifact_citations(kind):
    src = source()
    artifact = generate_study_artifact(source=src, track="medicine",
        artifact_type=kind, provider=Provider())
    assert artifact.items[0].segment_ids == (src.segments[0].segment_id,)
    assert [src.segment(ref).page for ref in artifact.items[0].segment_ids] == [4]

@pytest.mark.parametrize("kind", [StudyArtifactType.REVISION_NOTE, StudyArtifactType.MIND_MAP])
def test_rejects_fabricated_segments(kind):
    with pytest.raises(ValueError, match="Unverifiable"):
        generate_study_artifact(source=source(), track="medicine",
            artifact_type=kind, provider=Provider(bad=True))
