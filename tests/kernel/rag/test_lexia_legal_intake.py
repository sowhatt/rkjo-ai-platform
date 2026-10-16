"""Legal intake checks before any indexing or promotion."""
import hashlib
from datetime import date

import pytest

from rkjo_kernel.rag.legal_intake import prepare_legal_intake


TODAY = date(2026, 10, 16)
DOCUMENT = b"Fictional legal test source, not official."
HASH = hashlib.sha256(DOCUMENT).hexdigest()


def data():
    return {
        "tenant_id": "cabinet-a", "canonical_id": "BJ:DEMO:1",
        "title": "Fictional", "article": "Article demo", "source": "fixture",
        "official_source_url": "https://example.org/fixture.pdf",
        "checksum_sha256": HASH, "effective_from": "2020-01-01",
        "verification_status": "unverified", "status": "IN_FORCE",
        "domain": "droit", "country": "BJ",
    }


def test_matching_bytes_wait_for_human_review():
    packet = prepare_legal_intake(
        document=DOCUMENT, metadata=data(),
        authenticated_tenant_id="cabinet-a", on_date=TODAY,
    )
    assert packet.state == "awaiting_human_review"
    assert packet.reasons == ()
    assert packet.document_sha256 == HASH
    assert not packet.can_index_as_verified


def test_claimed_verification_is_downgraded():
    metadata = data()
    metadata["verification_status"] = "verified_content"
    packet = prepare_legal_intake(
        document=DOCUMENT, metadata=metadata,
        authenticated_tenant_id="cabinet-a", on_date=TODAY,
    )
    assert packet.metadata["verification_status"] == "unverified"
    assert not packet.can_index_as_verified


def test_checksum_mismatch_is_quarantined():
    metadata = data()
    metadata["checksum_sha256"] = "a" * 64
    packet = prepare_legal_intake(
        document=DOCUMENT, metadata=metadata,
        authenticated_tenant_id="cabinet-a", on_date=TODAY,
    )
    assert packet.state == "quarantined"
    assert "checksum_mismatch" in packet.reasons
    assert packet.metadata["checksum_sha256"] == HASH


def test_cross_tenant_claim_fails_closed():
    metadata = data()
    metadata["tenant_id"] = "cabinet-b"
    with pytest.raises(PermissionError):
        prepare_legal_intake(
            document=DOCUMENT, metadata=metadata,
            authenticated_tenant_id="cabinet-a", on_date=TODAY,
        )


def test_authenticated_tenant_is_injected_if_absent():
    metadata = data()
    del metadata["tenant_id"]
    packet = prepare_legal_intake(
        document=DOCUMENT, metadata=metadata,
        authenticated_tenant_id="cabinet-a", on_date=TODAY,
    )
    assert packet.metadata["tenant_id"] == "cabinet-a"


def test_absent_identity_or_empty_file_rejected():
    with pytest.raises(ValueError):
        prepare_legal_intake(
            document=DOCUMENT, metadata=data(),
            authenticated_tenant_id="", on_date=TODAY,
        )
    with pytest.raises(ValueError):
        prepare_legal_intake(
            document=b"", metadata=data(),
            authenticated_tenant_id="cabinet-a", on_date=TODAY,
        )


def test_repealed_source_is_quarantined():
    metadata = data()
    metadata["status"] = "REPEALED"
    packet = prepare_legal_intake(
        document=DOCUMENT, metadata=metadata,
        authenticated_tenant_id="cabinet-a", on_date=TODAY,
    )
    assert "status_not_in_force" in packet.reasons
    assert packet.state == "quarantined"
