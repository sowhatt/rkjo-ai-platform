"""Prepare (but NEVER index) legal documents for human intake review.

This component is independent of HTTP and persistence. Only an authenticated
backend caller can provide tenant_id; do not take it from client JSON.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

from rkjo_kernel.rag.legal_source_gate import assess_legal_source


@dataclass(frozen=True, slots=True)
class LegalIntakePacket:
    metadata: dict[str, str]
    document_sha256: str
    state: str
    reasons: tuple[str, ...]
    can_index_as_verified: bool = False


def prepare_legal_intake(
    *, document: bytes, metadata: dict, authenticated_tenant_id: str,
    on_date: date,
) -> LegalIntakePacket:
    """Compute actual bytes hash and fail closed on conflicting claims.

    No document bytes leave this call, no write to RAG or to any database
    occurs; a separate authorized process must review sources and publish.
    """
    if not isinstance(authenticated_tenant_id, str) or not authenticated_tenant_id.strip():
        raise ValueError("Authenticated tenant is required")
    if not isinstance(document, bytes) or not document:
        raise ValueError("Nonempty document bytes are required")
    if not isinstance(metadata, dict):
        raise ValueError("Metadata must be a dict")

    tenant = authenticated_tenant_id.strip()
    claimed_tenant = metadata.get("tenant_id")
    if claimed_tenant is not None and claimed_tenant != tenant:
        raise PermissionError("Cross-tenant intake is prohibited")

    actual_hash = hashlib.sha256(document).hexdigest()
    claimed_hash = metadata.get("checksum_sha256")
    reasons: list[str] = []
    if claimed_hash is not None and claimed_hash != actual_hash:
        reasons.append("checksum_mismatch")

    proposed = dict(metadata)
    proposed["tenant_id"] = tenant
    proposed["checksum_sha256"] = actual_hash

    # No caller supplied review status can upgrade legal trust.
    proposed["verification_status"] = "unverified"

    assessment = assess_legal_source(proposed, on_date=on_date)
    reasons.extend(assessment.reasons)
    return LegalIntakePacket(
        metadata=proposed,
        document_sha256=actual_hash,
        state="awaiting_human_review" if not reasons else "quarantined",
        reasons=tuple(dict.fromkeys(reasons)),
    )
