from datetime import (
    UTC,
    datetime,
)

from rkjo_kernel.rag.document_version_history import (
    DocumentVersionHistoryService,
)
from rkjo_kernel.rag.document_versioning import (
    DocumentVersion,
    DocumentVersionState,
)


NOW = datetime.now(UTC)


class FakeRepository:
    def __init__(
        self,
        *,
        state=None,
        versions=None,
    ):
        self.state = state
        self.versions = versions or []
        self.state_calls = []
        self.version_calls = []

    def get_document_state(
        self,
        *,
        document_id,
        tenant_id,
    ):
        self.state_calls.append(
            (
                document_id,
                tenant_id,
            )
        )
        return self.state

    def list_versions(
        self,
        *,
        document_id,
        tenant_id,
    ):
        self.version_calls.append(
            (
                document_id,
                tenant_id,
            )
        )
        return self.versions


def test_history_returns_current_version_and_versions():
    repository = FakeRepository(
        state=DocumentVersionState(
            document_id="doc-1",
            tenant_id="tenant-a",
            current_version=2,
            created_at=NOW,
            updated_at=NOW,
        ),
        versions=[
            DocumentVersion(
                version_id="v1",
                document_id="doc-1",
                tenant_id="tenant-a",
                version_number=1,
                content_hash="a" * 64,
                created_at=NOW,
            ),
            DocumentVersion(
                version_id="v2",
                document_id="doc-1",
                tenant_id="tenant-a",
                version_number=2,
                content_hash="b" * 64,
                created_at=NOW,
            ),
        ],
    )

    service = DocumentVersionHistoryService(
        repository=repository
    )

    result = service.get_history(
        document_id="doc-1",
        tenant_id="tenant-a",
    )

    assert result is not None
    assert result.current_version == 2

    assert [
        item.version_number
        for item in result.versions
    ] == [1, 2]


def test_missing_document_returns_none():
    repository = FakeRepository(
        state=None
    )

    service = DocumentVersionHistoryService(
        repository=repository
    )

    result = service.get_history(
        document_id="doc-1",
        tenant_id="tenant-a",
    )

    assert result is None
    assert repository.version_calls == []
