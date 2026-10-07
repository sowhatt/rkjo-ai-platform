import pytest

from rkjo_kernel.artifacts.models import Artifact, ArtifactModality
from rkjo_kernel.artifacts.relations import ArtifactRelationType, relate


def artifact(artifact_id, *, tenant="tenant-a", mission="mission-1", trace="trace-1"):
    return Artifact(
        artifact_id=artifact_id,
        modality=ArtifactModality.DOCUMENT,
        tenant_id=tenant,
        mission_id=mission,
        trace_id=trace,
        content="content",
    )


def test_provenance_relation_preserves_identity():
    relation = relate(
        parent=artifact("pdf"),
        child=artifact("ocr"),
        relation_type=ArtifactRelationType.OCR_OF,
        metadata={"page": 4},
    )
    assert relation.parent_artifact_id == "pdf"
    assert relation.child_artifact_id == "ocr"
    assert relation.tenant_id == "tenant-a"
    assert relation.mission_id == "mission-1"
    assert relation.trace_id == "trace-1"
    assert relation.metadata["page"] == 4


def test_provenance_rejects_cross_tenant_relation():
    with pytest.raises(ValueError, match="Cross-tenant"):
        relate(
            parent=artifact("a", tenant="tenant-a"),
            child=artifact("b", tenant="tenant-b"),
            relation_type=ArtifactRelationType.DERIVED_FROM,
        )


def test_provenance_rejects_mission_or_trace_mismatch():
    with pytest.raises(ValueError, match="mission_id"):
        relate(
            parent=artifact("a"),
            child=artifact("b", mission="mission-2"),
            relation_type=ArtifactRelationType.EXTRACTED_FROM,
        )
    with pytest.raises(ValueError, match="trace_id"):
        relate(
            parent=artifact("a"),
            child=artifact("b", trace="trace-2"),
            relation_type=ArtifactRelationType.FRAME_OF,
        )


def test_relation_rejects_self_reference():
    item = artifact("same")
    with pytest.raises(ValueError, match="itself"):
        relate(
            parent=item,
            child=item,
            relation_type=ArtifactRelationType.DERIVED_FROM,
        )
