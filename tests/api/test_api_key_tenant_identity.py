from rkjo_api.security import (
    resolve_api_tenant,
)


def test_viewer_api_key_resolves_tenant(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_VIEWER_API_KEY",
        "viewer-secret",
    )

    monkeypatch.setenv(
        "RKJO_VIEWER_TENANT_ID",
        "tenant-a",
    )

    assert (
        resolve_api_tenant(
            "viewer-secret"
        )
        == "tenant-a"
    )


def test_unconfigured_api_key_tenant_is_none(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_VIEWER_API_KEY",
        "viewer-secret",
    )

    monkeypatch.delenv(
        "RKJO_VIEWER_TENANT_ID",
        raising=False,
    )

    assert (
        resolve_api_tenant(
            "viewer-secret"
        )
        is None
    )
