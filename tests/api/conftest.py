import pytest


@pytest.fixture(autouse=True)
def configured_api_keys(
    monkeypatch,
):
    # Legacy key remains admin-compatible.
    monkeypatch.setenv(
        "RKJO_API_KEY",
        "rkjo-test-api-key",
    )

    monkeypatch.setenv(
        "RKJO_VIEWER_API_KEY",
        "rkjo-viewer-key",
    )

    monkeypatch.setenv(
        "RKJO_OPERATOR_API_KEY",
        "rkjo-operator-key",
    )

    monkeypatch.setenv(
        "RKJO_ADMIN_API_KEY",
        "rkjo-admin-key",
    )
