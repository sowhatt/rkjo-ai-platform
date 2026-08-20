from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocumentRestoreResult:
    document_id: str
    restored_from_version: int
    new_version: int
    content_hash: str
    chunk_count: int
