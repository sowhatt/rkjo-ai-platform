"""Privacy and PII sanitization primitives for RAG ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import hmac
import re


class SanitizationMode(StrEnum):
    NONE = "none"
    REDACT = "redact"
    PSEUDONYMIZE = "pseudonymize"


class PIICategory(StrEnum):
    EMAIL = "email"
    PHONE = "phone"
    IBAN = "iban"
    IPV4 = "ipv4"


@dataclass(frozen=True, slots=True)
class SanitizationResult:
    """Safe result returned by a document sanitizer.

    Important:
    no original PII values are retained in this object.
    """

    content: str
    detection_count: int
    categories: tuple[str, ...]
    mode: SanitizationMode


class DocumentSanitizer(ABC):
    """Contract applied before hashing, chunking and embedding."""

    @abstractmethod
    def sanitize(
        self,
        text: str,
    ) -> SanitizationResult:
        raise NotImplementedError


class NoOpDocumentSanitizer(
    DocumentSanitizer
):
    """Preserve content for public/non-sensitive documents."""

    def sanitize(
        self,
        text: str,
    ) -> SanitizationResult:
        return SanitizationResult(
            content=text,
            detection_count=0,
            categories=(),
            mode=SanitizationMode.NONE,
        )


class RuleBasedPIISanitizer(
    DocumentSanitizer
):
    """Sanitize common structured personal identifiers.

    Phase 5A intentionally focuses on deterministic patterns.
    Person names and contextual identifiers require a later
    NER/privacy engine.
    """

    _PATTERNS = (
        (
            PIICategory.EMAIL,
            re.compile(
                r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
                r"@"
                r"[A-Z0-9]"
                r"(?:[A-Z0-9-]{0,61}[A-Z0-9])?"
                r"(?:\."
                r"[A-Z0-9]"
                r"(?:[A-Z0-9-]{0,61}[A-Z0-9])?"
                r")+",
                re.IGNORECASE,
            ),
        ),
        (
            PIICategory.IBAN,
            re.compile(
                r"\b[A-Z]{2}\d{2}"
                r"(?:[ ]?[A-Z0-9]){11,30}\b",
                re.IGNORECASE,
            ),
        ),
        (
            PIICategory.IPV4,
            re.compile(
                r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
            ),
        ),
        (
            PIICategory.PHONE,
            re.compile(
                r"(?<!\w)"
                r"(?:\+?\d[\d .()\-]{6,}\d)"
                r"(?!\w)"
            ),
        ),
    )

    def __init__(
        self,
        *,
        mode: SanitizationMode = SanitizationMode.REDACT,
        pseudonymization_secret: str | None = None,
    ) -> None:
        if mode == SanitizationMode.NONE:
            raise ValueError(
                "Use NoOpDocumentSanitizer for NONE mode."
            )

        if (
            mode
            == SanitizationMode.PSEUDONYMIZE
            and (
                pseudonymization_secret is None
                or not pseudonymization_secret.strip()
            )
        ):
            raise ValueError(
                "pseudonymization_secret is required "
                "for pseudonymization."
            )

        self.mode = mode
        self._secret = (
            pseudonymization_secret
            or ""
        ).encode("utf-8")

    def sanitize(
        self,
        text: str,
    ) -> SanitizationResult:
        if not text:
            return SanitizationResult(
                content="",
                detection_count=0,
                categories=(),
                mode=self.mode,
            )

        sanitized = text
        detection_count = 0
        detected_categories: set[str] = set()

        for category, pattern in self._PATTERNS:

            def replace(
                match: re.Match[str],
                *,
                pii_category: PIICategory = category,
            ) -> str:
                nonlocal detection_count

                detection_count += 1
                detected_categories.add(
                    pii_category.value
                )

                return self._replacement(
                    pii_category,
                    match.group(0),
                )

            sanitized = pattern.sub(
                replace,
                sanitized,
            )

        return SanitizationResult(
            content=sanitized,
            detection_count=detection_count,
            categories=tuple(
                sorted(
                    detected_categories
                )
            ),
            mode=self.mode,
        )

    def _replacement(
        self,
        category: PIICategory,
        value: str,
    ) -> str:
        label = category.value.upper()

        if self.mode == SanitizationMode.REDACT:
            return f"[{label}]"

        digest = hmac.new(
            self._secret,
            value.strip().lower().encode(
                "utf-8"
            ),
            hashlib.sha256,
        ).hexdigest()[:12]

        return (
            f"[{label}_{digest}]"
        )
