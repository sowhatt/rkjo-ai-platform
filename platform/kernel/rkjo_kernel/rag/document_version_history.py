"""RAG document version history service."""

from __future__ import annotations

from dataclasses import dataclass

from rkjo_kernel.rag.document_versioning import (
    DocumentVersion,
)
from rkjo_kernel.rag.postgres_document_versioning import (
    PostgresDocumentVersionRepository,
)


@dataclass(frozen=True, slots=True)
class DocumentVersionHistory:
    document_id: str
    tenant_id: str
    current_version: int
    versions: tuple[DocumentVersion, ...]





@dataclass(frozen=True, slots=True)
class DocumentVersionDetail:
    document_id: str
    tenant_id: str
    version: DocumentVersion
    is_current: bool


class DocumentVersionHistoryService:
    """Read tenant-scoped document version history."""

    def __init__(
        self,
        *,
        repository: PostgresDocumentVersionRepository,
    ) -> None:
        self.repository = repository



    def get_version(
        self,
        *,
        document_id: str,
        tenant_id: str,
        version_number: int,
    ) -> DocumentVersionDetail | None:
        """Read one exact tenant-scoped version."""

        normalized_document_id = (
            document_id.strip()
        )
        normalized_tenant_id = (
            tenant_id.strip()
        )

        if not normalized_document_id:
            raise ValueError(
                "document_id must not be empty."
            )

        if not normalized_tenant_id:
            raise ValueError(
                "tenant_id must not be empty."
            )

        if version_number < 1:
            raise ValueError(
                "version_number must be greater than or equal to 1."
            )

        state = (
            self.repository.get_document_state(
                document_id=(
                    normalized_document_id
                ),
                tenant_id=(
                    normalized_tenant_id
                ),
            )
        )

        if state is None:
            return None

        version = self.repository.get_version(
            document_id=(
                normalized_document_id
            ),
            tenant_id=(
                normalized_tenant_id
            ),
            version_number=version_number,
        )

        if version is None:
            return None

        return DocumentVersionDetail(
            document_id=(
                normalized_document_id
            ),
            tenant_id=(
                normalized_tenant_id
            ),
            version=version,
            is_current=(
                version.version_number
                == state.current_version
            ),
        )

    def get_history(
        self,
        *,
        document_id: str,
        tenant_id: str,
    ) -> DocumentVersionHistory | None:
        normalized_document_id = (
            document_id.strip()
        )
        normalized_tenant_id = (
            tenant_id.strip()
        )

        if not normalized_document_id:
            raise ValueError(
                "document_id must not be empty."
            )

        if not normalized_tenant_id:
            raise ValueError(
                "tenant_id must not be empty."
            )

        state = (
            self.repository.get_document_state(
                document_id=(
                    normalized_document_id
                ),
                tenant_id=(
                    normalized_tenant_id
                ),
            )
        )

        if state is None:
            return None

        versions = (
            self.repository.list_versions(
                document_id=(
                    normalized_document_id
                ),
                tenant_id=(
                    normalized_tenant_id
                ),
            )
        )

        return DocumentVersionHistory(
            document_id=(
                normalized_document_id
            ),
            tenant_id=(
                normalized_tenant_id
            ),
            current_version=(
                state.current_version
            ),
            versions=tuple(versions),
        )
