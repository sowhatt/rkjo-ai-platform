"""Provenance relations between multimodal RKJO artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4

from rkjo_kernel.artifacts.models import Artifact


class ArtifactRelationType(str, Enum):
    DERIVED_FROM = "derived_from"
    EXTRACTED_FROM = "extracted_from"
    TRANSCRIBED_FROM = "transcribed_from"
    OCR_OF = "ocr_of"
    FRAME_OF = "frame_of"
    SCENE_OF = "scene_of"


@dataclass(frozen=True, slots=True)
class ArtifactRelation:
    parent_artifact_id: str
    child_artifact_id: str
    tenant_id: str
    relation_type: ArtifactRelationType
    relation_id: str = field(default_factory=lambda: str(uuid4()))
    mission_id: str | None = None
    trace_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.parent_artifact_id.strip() or not self.child_artifact_id.strip():
            raise ValueError("ArtifactRelation requires parent and child artifact ids.")
        if self.parent_artifact_id == self.child_artifact_id:
            raise ValueError("ArtifactRelation cannot reference itself.")
        if not self.tenant_id.strip():
            raise ValueError("ArtifactRelation requires tenant_id.")


def relate(
    *,
    parent: Artifact,
    child: Artifact,
    relation_type: ArtifactRelationType,
    metadata: Mapping[str, Any] | None = None,
) -> ArtifactRelation:
    """Create a fail-closed provenance relation preserving canonical identity."""
    if parent.tenant_id != child.tenant_id:
        raise ValueError("Cross-tenant artifact relations are forbidden.")
    if parent.mission_id != child.mission_id:
        raise ValueError("Artifact relation mission_id mismatch.")
    if parent.trace_id != child.trace_id:
        raise ValueError("Artifact relation trace_id mismatch.")
    return ArtifactRelation(
        parent_artifact_id=parent.artifact_id,
        child_artifact_id=child.artifact_id,
        tenant_id=parent.tenant_id,
        mission_id=parent.mission_id,
        trace_id=parent.trace_id,
        relation_type=relation_type,
        metadata=dict(metadata or {}),
    )
