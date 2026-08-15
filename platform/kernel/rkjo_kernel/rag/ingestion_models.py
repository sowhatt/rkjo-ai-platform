from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class LoadedDocument:
    content: str
    source_path: Path
    source_type: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError(
                "Loaded document content must not be empty."
            )


@dataclass(frozen=True, slots=True)
class IngestionResult:
    document_id: str
    content_hash: str
    chunk_count: int
    duplicate: bool
