import pytest


@pytest.fixture(autouse=True)
def configured_api_key(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_API_KEY",
        "rkjo-test-api-key",
    )
