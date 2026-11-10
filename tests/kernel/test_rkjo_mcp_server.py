import pytest

from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.tools.approval import InMemoryToolApprovalStore, ToolApprovalService
from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.descriptor import ToolDescriptor
from rkjo_kernel.tools.invoker import ToolInvoker
from rkjo_kernel.tools.mcp.server import RKJOMCPServer
from rkjo_kernel.tools.registry import ToolRegistry


def make_server(*, sensitive=False):
    registry = ToolRegistry()
    calls = []
    registry.register(
        ToolDescriptor(
            name="finance.refund",
            display_name="Refund",
            description="Refund an order",
            input_schema={"type": "object"},
            metadata={"requires_approval": sensitive},
        ),
        handler=lambda payload, context: calls.append(
            (payload, context.tenant_id)
        ) or {"refunded": True},
    )
    capability = AgentCapability(
        name="refund_order",
        description="Refund an order",
        tools=["finance.refund"],
    )
    approvals = ToolApprovalService(InMemoryToolApprovalStore())
    server = RKJOMCPServer(
        registry=registry,
        invoker=ToolInvoker(registry, approval_service=approvals),
        capabilities=[capability],
        exposed_capabilities={"refund_order"},
    )
    return server, calls, approvals


def context(**metadata):
    return ToolExecutionContext(
        tenant_id="tenant-a",
        agent_name="external.mcp",
        capability_name="refund_order",
        mission_id="Mission-1",
        trace_id="Trace-1",
        metadata=metadata,
    )


def test_mcp_server_lists_only_explicitly_exposed_capability_tools():
    server, _, _ = make_server()
    result = server.handle(method="tools/list")
    assert result["tools"] == [{
        "name": "rkjo.refund_order.finance_refund",
        "description": "Refund an order",
        "inputSchema": {"type": "object"},
    }]


def test_mcp_server_executes_through_authorized_tool_gateway():
    server, calls, _ = make_server()
    result = server.handle(
        method="tools/call",
        params={
            "name": "rkjo.refund_order.finance_refund",
            "arguments": {"order_id": "o-1"},
        },
        context=context(),
    )
    assert result["content"] == {"refunded": True}
    assert calls == [({"order_id": "o-1"}, "tenant-a")]


def test_mcp_server_rejects_unexposed_tool_and_missing_context():
    server, calls, _ = make_server()
    with pytest.raises(PermissionError):
        server.handle(
            method="tools/call",
            params={"name": "rkjo.other.secret", "arguments": {}},
            context=context(),
        )
    with pytest.raises(PermissionError):
        server.handle(
            method="tools/call",
            params={
                "name": "rkjo.refund_order.finance_refund",
                "arguments": {},
            },
            context=None,
        )
    assert calls == []


def test_mcp_server_preserves_durable_hitl_for_sensitive_tool():
    server, calls, approvals = make_server(sensitive=True)

    with pytest.raises(PermissionError, match="durable approval"):
        server.handle(
            method="tools/call",
            params={
                "name": "rkjo.refund_order.finance_refund",
                "arguments": {"order_id": "o-1"},
            },
            context=context(),
        )
    assert calls == []

    approval = approvals.request(
        tenant_id="tenant-a",
        tool_name="finance.refund",
        mission_id="Mission-1",
        trace_id="Trace-1",
    )
    approvals.decide(
        approval_id=approval.approval_id,
        tenant_id="tenant-a",
        approved=True,
        decided_by="reviewer",
    )

    result = server.handle(
        method="tools/call",
        params={
            "name": "rkjo.refund_order.finance_refund",
            "arguments": {"order_id": "o-1"},
        },
        context=context(approval_id=approval.approval_id),
    )
    assert result["content"] == {"refunded": True}
    assert len(calls) == 1


def test_mcp_server_rejects_context_capability_mismatch():
    server, calls, _ = make_server()
    wrong = ToolExecutionContext(
        tenant_id="tenant-a",
        agent_name="external.mcp",
        capability_name="another_capability",
    )
    with pytest.raises(PermissionError, match="does not match"):
        server.handle(
            method="tools/call",
            params={
                "name": "rkjo.refund_order.finance_refund",
                "arguments": {},
            },
            context=wrong,
        )
    assert calls == []
