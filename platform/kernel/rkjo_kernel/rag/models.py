"""Core RAG domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class Document:
    """Source document ingested into the knowledge layer."""

    content: str
    document_id: str = field(
        default_factory=lambda: str(uuid4())
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError(
                "Document content must not be empty."
            )

        if not self.document_id.strip():
            raise ValueError(
                "Document id must not be empty."
            )


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """One searchable document fragment."""

    document_id: str
    content: str
    chunk_index: int
    chunk_id: str = field(
        default_factory=lambda: str(uuid4())
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.document_id.strip():
            raise ValueError(
                "Chunk document_id must not be empty."
            )

        if not self.content.strip():
            raise ValueError(
                "Chunk content must not be empty."
            )

        if self.chunk_index < 0:
            raise ValueError(
                "Chunk index must not be negative."
            )


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """Chunk returned by semantic retrieval."""

    chunk: DocumentChunk
    score: float
