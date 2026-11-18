import pytest

from rkjo_kernel.tools.mcp.security import (
    MCPPrincipal,
    MCPServerSecurity,
    MappingMCPAuthenticator,
)


def security():
    return MCPServerSecurity(
        MappingMCPAuthenticator({
            "secret-a": MCPPrincipal(
                principal_id="client-a",
                tenant_id="tenant-a",
                allowed_capabilities=frozenset({"refund_order", "catalog_read"}),
            ),
            "secret-b": MCPPrincipal(
                principal_id="client-b",
                tenant_id="tenant-b",
                allowed_capabilities=frozenset({"catalog_read"}),
            ),
        })
    )


def test_authenticated_principal_builds_canonical_tenant_context():
    context = security().authorize(
        credential="secret-a",
        capability_name="refund_order",
        agent_name="external.mcp",
        mission_id="Mission-A",
        trace_id="Trace-A",
        metadata={
            "mcp_principal_id": "forged-client",
            "mcp_authenticated_tenant_id": "tenant-b",
            "tenant_id": "tenant-b",
        },
    )
    assert context.tenant_id == "tenant-a"
    assert context.capability_name == "refund_order"
    assert context.mission_id == "Mission-A"
    assert context.trace_id == "Trace-A"
    assert context.metadata["mcp_principal_id"] == "client-a"
    assert context.metadata["mcp_authenticated_tenant_id"] == "tenant-a"


@pytest.mark.parametrize("credential", ["", "unknown-secret"])
def test_missing_or_invalid_credentials_fail_closed(credential):
    with pytest.raises(PermissionError):
        security().authorize(
            credential=credential,
            capability_name="catalog_read",
            agent_name="external.mcp",
        )


def test_principal_cannot_use_capability_outside_scope():
    with pytest.raises(PermissionError, match="not authorized"):
        security().authorize(
            credential="secret-b",
            capability_name="refund_order",
            agent_name="external.mcp",
        )


def test_principal_tenant_cannot_be_overridden_by_caller_metadata():
    context = security().authorize(
        credential="secret-b",
        capability_name="catalog_read",
        agent_name="external.mcp",
        metadata={"tenant_id": "tenant-a"},
    )
    assert context.tenant_id == "tenant-b"
    assert context.metadata["tenant_id"] == "tenant-a"
    assert context.metadata["mcp_authenticated_tenant_id"] == "tenant-b"
