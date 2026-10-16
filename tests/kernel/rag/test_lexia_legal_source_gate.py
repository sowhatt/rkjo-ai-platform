"""Legal corpus metadata assessment: structural checks, never self-verification."""
from datetime import date

from rkjo_kernel.rag.legal_source_gate import assess_legal_source


def sample():
    return {
        "tenant_id": "cabinet-test",
        "canonical_id": "BJ:EXAMPLE:1",
        "title": "Texte fictif pour tests",
        "article": "Article X",
        "source": "source-test",
        "official_source_url": "https://example.org/fiction.pdf",
        "checksum_sha256": "a" * 64,
        "effective_from": "2020-01-01",
        "effective_to": "",
        "domain": "droit",
        "country": "BJ",
        "status": "IN_FORCE",
        "verification_status": "unverified",
    }


def test_structurally_complete_source_is_only_a_review_candidate():
    decision = assess_legal_source(sample(), on_date=date(2026, 10, 16))
    assert decision.admissible_for_review
    assert not decision.trusted_for_citation
    assert decision.reasons == ()


def test_self_declared_verification_never_establishes_trust():
    metadata = sample()
    metadata["verification_status"] = "verified_content"
    decision = assess_legal_source(metadata, on_date=date(2026, 10, 16))
    assert decision.admissible_for_review
    assert not decision.trusted_for_citation


def test_missing_tenant_and_source_are_quarantined():
    metadata = sample()
    metadata.pop("tenant_id")
    metadata["source"] = " "
    decision = assess_legal_source(metadata, on_date=date(2026, 10, 16))
    assert not decision.admissible_for_review
    assert "missing_or_invalid:tenant_id" in decision.reasons
    assert "missing_or_invalid:source" in decision.reasons


def test_invalid_hash_url_and_country_are_rejected():
    metadata = sample()
    metadata["checksum_sha256"] = "fake"
    metadata["official_source_url"] = "http://invalid.test/doc"
    metadata["country"] = "FR"
    decision = assess_legal_source(metadata, on_date=date(2026, 10, 16))
    assert not decision.admissible_for_review
    assert {"invalid_checksum", "invalid_source_url", "wrong_country"}.issubset(
        set(decision.reasons)
    )


def test_future_and_expired_sources_are_rejected():
    future = sample()
    future["effective_from"] = "2027-01-01"
    assert "not_yet_effective" in assess_legal_source(
        future, on_date=date(2026, 10, 16)
    ).reasons

    expired = sample()
    expired["effective_to"] = "2025-01-01"
    assert "expired" in assess_legal_source(
        expired, on_date=date(2026, 10, 16)
    ).reasons


def test_private_notarial_act_and_repealed_law_are_rejected():
    metadata = sample()
    metadata["domaine"] = "actes_notariaux_beninois"
    metadata["status"] = "REPEALED"
    decision = assess_legal_source(metadata, on_date=date(2026, 10, 16))
    assert not decision.admissible_for_review
    assert "private_act_not_authority" in decision.reasons
    assert "status_not_in_force" in decision.reasons


def test_benin_and_ohada_are_supported_as_distinct_jurisdictions():
    metadata = sample()
    metadata["country"] = "OHADA"
    assert assess_legal_source(metadata, on_date=date(2026, 10, 16)).admissible_for_review


def test_bad_dates_and_review_status_are_rejected():
    metadata = sample()
    metadata["effective_from"] = "2026-02-30"
    metadata["verification_status"] = "verified"
    decision = assess_legal_source(metadata, on_date=date(2026, 10, 16))
    assert "invalid_effective_date" in decision.reasons
    assert "invalid_review_status" in decision.reasons
