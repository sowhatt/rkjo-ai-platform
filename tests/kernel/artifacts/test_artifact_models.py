import pytest

from rkjo_kernel.artifacts.models import (
    Artifact,
    ArtifactModality,
    ArtifactSegment,
    ArtifactSource,
)


def test_artifact_supports_document_identity_and_source():
    artifact = Artifact(
        modality=ArtifactModality.DOCUMENT,
        tenant_id="tenant-a",
        mission_id="mission-1",
        trace_id="trace-1",
        source=ArtifactSource(
            filename="invoice.pdf",
            mime_type="application/pdf",
        ),
        metadata={"domain": "assurance"},
    )
    assert artifact.artifact_id
    assert artifact.source.filename == "invoice.pdf"
    assert artifact.mission_id == "mission-1"


def test_artifact_requires_content_or_source():
    with pytest.raises(ValueError):
        Artifact(
            modality=ArtifactModality.IMAGE,
            tenant_id="tenant-a",
        )


def test_artifact_segment_supports_page_and_time_ranges():
    page = ArtifactSegment(
        artifact_id="artifact-1",
        tenant_id="tenant-a",
        text="page text",
        page=2,
    )
    timeline = ArtifactSegment(
        artifact_id="artifact-2",
        tenant_id="tenant-a",
        text="speech",
        start_ms=1000,
        end_ms=2500,
    )
    assert page.page == 2
    assert (timeline.start_ms, timeline.end_ms) == (1000, 2500)


def test_artifact_segment_rejects_invalid_time_range():
    with pytest.raises(ValueError):
        ArtifactSegment(
            artifact_id="artifact-1",
            tenant_id="tenant-a",
            text="bad",
            start_ms=3000,
            end_ms=1000,
        )
