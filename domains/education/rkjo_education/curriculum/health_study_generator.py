"""A safe deterministic baseline for student-created text course summaries.

This module does not invoke an LLM; it demonstrates provenance-preserving
contracts that a specialised model provider must satisfy later.
"""
from __future__ import annotations

from rkjo_education.curriculum.study_sources import StudySourcePackage
from rkjo_education.curriculum.study_artifacts import (
    SourcedLearningItem, StudyArtifact, StudyArtifactType,
)


def make_revision_outline(source: StudySourcePackage) -> StudyArtifact:
    items = tuple(
        SourcedLearningItem(
            title=f"Document {source.document_id} — page {segment.page}",
            body=segment.text.strip()[:500],
            segment_ids=(segment.segment_id,),
        )
        for segment in source.segments
    )
    artifact = StudyArtifact(
        artifact_type=StudyArtifactType.REVISION_NOTE,
        source_document_id=source.document_id,
        source_version=source.version,
        items=items,
        generated_by="rkjo_deterministic_outline_v1",
    )
    artifact.validate_sources(source)
    return artifact
