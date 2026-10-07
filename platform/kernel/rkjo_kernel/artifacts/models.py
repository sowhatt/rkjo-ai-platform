"""Canonical multimodal artifact contracts for RKJO."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4


class ArtifactModality(str, Enum):
    TEXT = "text"
    DOCUMENT = "document"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    BINARY = "binary"


@dataclass(frozen=True, slots=True)
class ArtifactSource:
    uri: str | None = None
    filename: str | None = None
    mime_type: str | None = None

    def __post_init__(self) -> None:
        if self.uri is None and self.filename is None:
            raise ValueError("ArtifactSource requires uri or filename.")
        if self.mime_type is not None and not self.mime_type.strip():
            raise ValueError("ArtifactSource mime_type cannot be blank.")


@dataclass(frozen=True, slots=True)
class Artifact:
    modality: ArtifactModality
    tenant_id: str
    artifact_id: str = field(default_factory=lambda: str(uuid4()))
    mission_id: str | None = None
    trace_id: str | None = None
    source: ArtifactSource | None = None
    content: bytes | str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.artifact_id.strip():
            raise ValueError("Artifact requires artifact_id.")
        if not self.tenant_id.strip():
            raise ValueError("Artifact requires tenant_id.")
        if self.content is None and self.source is None:
            raise ValueError("Artifact requires content or source.")
        if isinstance(self.content, bytes) and not self.content:
            raise ValueError("Artifact byte content cannot be empty.")
        if isinstance(self.content, str) and not self.content.strip():
            raise ValueError("Artifact text content cannot be blank.")


@dataclass(frozen=True, slots=True)
class ArtifactSegment:
    artifact_id: str
    tenant_id: str
    segment_id: str = field(default_factory=lambda: str(uuid4()))
    mission_id: str | None = None
    trace_id: str | None = None
    text: str | None = None
    data: bytes | None = None
    page: int | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.segment_id.strip() or not self.artifact_id.strip():
            raise ValueError("ArtifactSegment requires segment_id and artifact_id.")
        if not self.tenant_id.strip():
            raise ValueError("ArtifactSegment requires tenant_id.")
        if self.text is None and self.data is None:
            raise ValueError("ArtifactSegment requires text or data.")
        if self.page is not None and self.page < 1:
            raise ValueError("ArtifactSegment page must be >= 1.")
        if self.start_ms is not None and self.start_ms < 0:
            raise ValueError("ArtifactSegment start_ms cannot be negative.")
        if self.end_ms is not None and self.end_ms < 0:
            raise ValueError("ArtifactSegment end_ms cannot be negative.")
        if self.start_ms is not None and self.end_ms is not None and self.end_ms < self.start_ms:
            raise ValueError("ArtifactSegment end_ms cannot precede start_ms.")
