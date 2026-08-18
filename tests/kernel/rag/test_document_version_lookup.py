from datetime import (
    UTC,
    datetime,
)

import pytest

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
        version=None,
    ):
        self.state = state
        self.version = version
        self.version_calls = []

    def get_document_state(
        self,
        *,
        document_id,
        tenant_id,
    ):
        return self.state

    def get_version(
        self,
        *,
        document_id,
        tenant_id,
        version_number,
    ):
        self.version_calls.append(
            (
                document_id,
                tenant_id,
                version_number,
            )
        )
        return self.version


def state(current_version=2):
    return DocumentVersionState(
        document_id="doc-1",
        tenant_id="tenant-a",
        current_version=current_version,
        created_at=NOW,
        updated_at=NOW,
    )


def version(number=2):
    return DocumentVersion(
        version_id="version-id",
        document_id="doc-1",
        tenant_id="tenant-a",
        version_number=number,
        content_hash="b" * 64,
        created_at=NOW,
    )


def test_get_current_version_detail():
    service = DocumentVersionHistoryService(
        repository=FakeRepository(
            state=state(2),
            version=version(2),
        )
    )

    result = service.get_version(
        document_id="doc-1",
        tenant_id="tenant-a",
        version_number=2,
    )

    assert result is not None
    assert result.version.version_number == 2
    assert result.is_current is True


def test_get_historical_version_detail():
    service = DocumentVersionHistoryService(
        repository=FakeRepository(
            state=state(3),
            version=version(2),
        )
    )

    result = service.get_version(
        document_id="doc-1",
        tenant_id="tenant-a",
        version_number=2,
    )

    assert result is not None
    assert result.is_current is False


def test_missing_version_returns_none():
    service = DocumentVersionHistoryService(
        repository=FakeRepository(
            state=state(3),
            version=None,
        )
    )

    result = service.get_version(
        document_id="doc-1",
        tenant_id="tenant-a",
        version_number=99,
    )

    assert result is None


def test_invalid_version_number_is_rejected():
    service = DocumentVersionHistoryService(
        repository=FakeRepository(
            state=state()
        )
    )

    with pytest.raises(
        ValueError,
        match="greater than or equal to 1",
    ):
        service.get_version(
            document_id="doc-1",
            tenant_id="tenant-a",
            version_number=0,
        )
