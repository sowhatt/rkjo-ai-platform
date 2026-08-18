"""RAG document versioning domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DocumentVersion:
    version_id: str
    document_id: str
    tenant_id: str
    version_number: int
    content_hash: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DocumentVersionState:
    document_id: str
    tenant_id: str
    current_version: int
    created_at: datetime
    updated_at: datetime
