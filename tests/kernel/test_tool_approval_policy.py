from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.tools.approval import (
    InMemoryToolApprovalStore,
    ToolApprovalService,
)
from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.descriptor import ToolDescriptor
from rkjo_kernel.tools.invoker import ToolInvoker
from rkjo_kernel.tools.registry import ToolRegistry


def setup():
    registry = ToolRegistry()
    calls = []
    registry.register(
        ToolDescriptor(
            name="payments.refund",
            display_name="Refund",
            description="Refund payment",
            metadata={"requires_approval": True},
        ),
        handler=lambda payload, context: calls.append(payload) or {"ok": True},
    )
    capability = AgentCapability(
        name="refund_payment",
        description="Refund a payment",
        tools=["payments.refund"],
    )
    approvals = ToolApprovalService(InMemoryToolApprovalStore())
    return registry, calls, capability, approvals


def context(**metadata):
    return ToolExecutionContext(
        tenant_id="tenant-a",
        agent_name="payments-agent",
        capability_name="refund_payment",
        mission_id="Mission-ABC",
        trace_id="Trace-XYZ",
        metadata=metadata,
    )


def test_sensitive_tool_fails_closed_without_approval():
    registry, calls, capability, approvals = setup()
    result = ToolInvoker(
        registry,
        approval_service=approvals,
    ).invoke_authorized(
        capability=capability,
        tool_name="payments.refund",
        payload={"amount": 100},
        context=context(),
    )
    assert result.success is False
    assert calls == []


def test_inline_approval_claim_is_never_trusted():
    registry, calls, capability, approvals = setup()
    result = ToolInvoker(
        registry,
        approval_service=approvals,
    ).invoke_authorized(
        capability=capability,
        tool_name="payments.refund",
        payload={"amount": 100},
        context=context(
            tool_approval={
                "tool_name": "payments.refund",
                "approved": True,
            }
        ),
    )
    assert result.success is False
    assert calls == []


def test_sensitive_tool_executes_with_matching_durable_approval():
    registry, calls, capability, approvals = setup()
    approval = approvals.request(
        tenant_id="tenant-a",
        tool_name="payments.refund",
        mission_id="Mission-ABC",
        trace_id="Trace-XYZ",
    )
    approval = approvals.decide(
        approval_id=approval.approval_id,
        tenant_id="tenant-a",
        approved=True,
        decided_by="reviewer",
    )
    result = ToolInvoker(
        registry,
        approval_service=approvals,
    ).invoke_authorized(
        capability=capability,
        tool_name="payments.refund",
        payload={"amount": 100},
        context=context(approval_id=approval.approval_id),
    )
    assert result.success is True
    assert calls == [{"amount": 100}]


def test_approval_from_another_mission_is_rejected():
    registry, calls, capability, approvals = setup()
    approval = approvals.request(
        tenant_id="tenant-a",
        tool_name="payments.refund",
        mission_id="Other-Mission",
        trace_id="Trace-XYZ",
    )
    approval = approvals.decide(
        approval_id=approval.approval_id,
        tenant_id="tenant-a",
        approved=True,
        decided_by="reviewer",
    )
    result = ToolInvoker(
        registry,
        approval_service=approvals,
    ).invoke_authorized(
        capability=capability,
        tool_name="payments.refund",
        payload={},
        context=context(approval_id=approval.approval_id),
    )
    assert result.success is False
    assert calls == []
