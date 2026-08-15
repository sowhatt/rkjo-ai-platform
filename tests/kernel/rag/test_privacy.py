import pytest

from rkjo_kernel.rag.privacy import (
    NoOpDocumentSanitizer,
    RuleBasedPIISanitizer,
    SanitizationMode,
)


def test_noop_preserves_content():
    sanitizer = (
        NoOpDocumentSanitizer()
    )

    result = sanitizer.sanitize(
        "public information"
    )

    assert result.content == (
        "public information"
    )

    assert result.detection_count == 0
    assert result.categories == ()
    assert (
        result.mode
        == SanitizationMode.NONE
    )


def test_redacts_email_phone_ip_and_iban():
    sanitizer = (
        RuleBasedPIISanitizer(
            mode=SanitizationMode.REDACT
        )
    )

    result = sanitizer.sanitize(
        (
            "Email jean@example.com. "
            "Phone +33 6 12 34 56 78. "
            "IP 192.168.1.25. "
            "IBAN FR7630006000011234567890189."
        )
    )

    assert "jean@example.com" not in (
        result.content
    )

    assert "+33 6 12 34 56 78" not in (
        result.content
    )

    assert "192.168.1.25" not in (
        result.content
    )

    assert (
        "FR7630006000011234567890189"
        not in result.content
    )

    assert "[EMAIL]" in result.content
    assert "[PHONE]" in result.content
    assert "[IPV4]" in result.content
    assert "[IBAN]" in result.content

    assert result.detection_count == 4

    assert set(
        result.categories
    ) == {
        "email",
        "phone",
        "ipv4",
        "iban",
    }


def test_pseudonymization_is_stable():
    sanitizer = (
        RuleBasedPIISanitizer(
            mode=(
                SanitizationMode.PSEUDONYMIZE
            ),
            pseudonymization_secret=(
                "test-secret"
            ),
        )
    )

    first = sanitizer.sanitize(
        "alice@example.com"
    )

    second = sanitizer.sanitize(
        "alice@example.com"
    )

    assert first.content == second.content
    assert "alice@example.com" not in (
        first.content
    )

    assert first.content.startswith(
        "[EMAIL_"
    )


def test_different_values_have_different_pseudonyms():
    sanitizer = (
        RuleBasedPIISanitizer(
            mode=(
                SanitizationMode.PSEUDONYMIZE
            ),
            pseudonymization_secret=(
                "test-secret"
            ),
        )
    )

    first = sanitizer.sanitize(
        "alice@example.com"
    )

    second = sanitizer.sanitize(
        "bob@example.com"
    )

    assert (
        first.content
        != second.content
    )


def test_pseudonymization_requires_secret():
    with pytest.raises(
        ValueError,
        match="secret",
    ):
        RuleBasedPIISanitizer(
            mode=(
                SanitizationMode.PSEUDONYMIZE
            )
        )
