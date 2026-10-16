"""Conservative metadata gate for a Bénin/OHADA legal reference.

Only checks structural provenance and review workflow status. The supplied
URL, checksum and declared effective dates are untrusted until independently
checked against authoritative records. No function in this module promotes
a source to verified status.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlsplit


SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
COUNTRIES = frozenset({"BJ", "OHADA"})
STATES = frozenset({"quarantined", "unverified", "verified_source", "verified_content"})
REQUIRED = ("tenant_id", "canonical_id", "title", "article", "source",
            "official_source_url", "checksum_sha256", "effective_from",
            "verification_status")


@dataclass(frozen=True, slots=True)
class LegalSourceDecision:
    admissible_for_review: bool
    trusted_for_citation: bool
    reasons: tuple[str, ...]


def assess_legal_source(metadata: dict, *, on_date: date) -> LegalSourceDecision:
    """Return review eligibility; never infer trust from self-declared metadata."""
    reasons: list[str] = []
    for field in REQUIRED:
        value = metadata.get(field)
        if not isinstance(value, str) or not value.strip():
            reasons.append(f"missing_or_invalid:{field}")

    if metadata.get("domain") != "droit":
        reasons.append("wrong_domain")
    if metadata.get("country") not in COUNTRIES:
        reasons.append("wrong_country")
    if metadata.get("domaine") == "actes_notariaux_beninois":
        reasons.append("private_act_not_authority")
    if metadata.get("verification_status") not in STATES:
        reasons.append("invalid_review_status")

    url = metadata.get("official_source_url")
    if isinstance(url, str) and url.strip():
        parts = urlsplit(url)
        if (parts.scheme != "https" or not parts.hostname
                or parts.username or parts.password or parts.fragment):
            reasons.append("invalid_source_url")
    digest = metadata.get("checksum_sha256")
    if isinstance(digest, str) and digest.strip() and not SHA256.fullmatch(digest):
        reasons.append("invalid_checksum")

    start = metadata.get("effective_from")
    end = metadata.get("effective_to")
    try:
        start_date = date.fromisoformat(start) if isinstance(start, str) and start else None
        end_date = date.fromisoformat(end) if isinstance(end, str) and end else None
    except ValueError:
        reasons.append("invalid_effective_date")
    else:
        if start_date and on_date < start_date:
            reasons.append("not_yet_effective")
        if end_date and on_date >= end_date:
            reasons.append("expired")
        if start_date and end_date and end_date <= start_date:
            reasons.append("invalid_effective_range")

    if metadata.get("status") not in {"IN_FORCE", "PARTIALLY_IN_FORCE"}:
        reasons.append("status_not_in_force")

    # Explicit policy: even a self-declared VERIFIED_CONTENT is never enough
    # for a verified legal citation. The legal authority system must compare
    # the real source bytes and applicable law independently.
    return LegalSourceDecision(
        admissible_for_review=not reasons,
        trusted_for_citation=False,
        reasons=tuple(dict.fromkeys(reasons)),
    )
