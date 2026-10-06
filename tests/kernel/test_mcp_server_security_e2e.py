from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.descriptor import ToolDescriptor
from rkjo_kernel.tools.invoker import ToolInvoker
from rkjo_kernel.tools.mcp.security import (
    MCPPrincipal,
    MCPServerSecurity,
    MappingMCPAuthenticator,
)
from rkjo_kernel.tools.mcp.server import RKJOMCPServer
from rkjo_kernel.tools.registry import ToolRegistry


def build_server():
    registry = ToolRegistry()
    executions = []

    def handler(payload, context: ToolExecutionContext):
        executions.append({
            "tenant_id": context.tenant_id,
            "principal_id": context.metadata.get("mcp_principal_id"),
            "authenticated_tenant": context.metadata.get(
                "mcp_authenticated_tenant_id"
            ),
            "caller_tenant_claim": context.metadata.get("tenant_id"),
            "payload": dict(payload),
        })
        return {"tenant_id": context.tenant_id, "ok": True}

    registry.register(
        ToolDescriptor(
            name="catalog.read",
            display_name="Catalog Read",
            description="Read tenant catalog",
            input_schema={"type": "object"},
        ),
        handler=handler,
    )

    capability = AgentCapability(
        name="catalog_read",
        description="Read catalog",
        tools=["catalog.read"],
    )

    security = MCPServerSecurity(
        MappingMCPAuthenticator({
            "credential-a": MCPPrincipal(
                principal_id="client-a",
                tenant_id="tenant-a",
                allowed_capabilities=frozenset({"catalog_read"}),
            ),
            "credential-b": MCPPrincipal(
                principal_id="client-b",
                tenant_id="tenant-b",
                allowed_capabilities=frozenset({"catalog_read"}),
            ),
        })
    )

    server = RKJOMCPServer(
        registry=registry,
        invoker=ToolInvoker(registry),
        capabilities=[capability],
        exposed_capabilities={"catalog_read"},
        security=security,
    )
    return server, executions


def test_authenticated_client_a_executes_only_as_tenant_a():
    server, executions = build_server()

    result = server.handle_authenticated(
        credential="credential-a",
        method="tools/call",
        capability_name="catalog_read",
        params={
            "name": "rkjo.catalog_read.catalog_read",
            "arguments": {"sku": "SKU-1"},
        },
        mission_id="Mission-A",
        trace_id="Trace-A",
    )

    assert result["content"] == {"tenant_id": "tenant-a", "ok": True}
    assert executions == [{
        "tenant_id": "tenant-a",
        "principal_id": "client-a",
        "authenticated_tenant": "tenant-a",
        "caller_tenant_claim": None,
        "payload": {"sku": "SKU-1"},
    }]


def test_client_a_cannot_impersonate_tenant_b_through_metadata():
    server, executions = build_server()

    result = server.handle_authenticated(
        credential="credential-a",
        method="tools/call",
        capability_name="catalog_read",
        params={
            "name": "rkjo.catalog_read.catalog_read",
            "arguments": {"sku": "SKU-2"},
        },
        metadata={
            "tenant_id": "tenant-b",
            "mcp_principal_id": "client-b",
            "mcp_authenticated_tenant_id": "tenant-b",
        },
    )

    assert result["content"]["tenant_id"] == "tenant-a"
    assert executions[0]["tenant_id"] == "tenant-a"
    assert executions[0]["principal_id"] == "client-a"
    assert executions[0]["authenticated_tenant"] == "tenant-a"
    # The untrusted claim may remain as evidence, but never becomes routing identity.
    assert executions[0]["caller_tenant_claim"] == "tenant-b"


def test_two_authenticated_clients_remain_tenant_isolated():
    server, executions = build_server()

    for credential in ("credential-a", "credential-b"):
        server.handle_authenticated(
            credential=credential,
            method="tools/call",
            capability_name="catalog_read",
            params={
                "name": "rkjo.catalog_read.catalog_read",
                "arguments": {},
            },
        )

    assert [item["tenant_id"] for item in executions] == [
        "tenant-a",
        "tenant-b",
    ]
    assert [item["principal_id"] for item in executions] == [
        "client-a",
        "client-b",
    ]
