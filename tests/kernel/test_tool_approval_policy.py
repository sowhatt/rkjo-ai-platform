from rkjo_kernel.registry.capability import AgentCapability
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
    return registry, calls, capability


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
    registry, calls, capability = setup()
    result = ToolInvoker(registry).invoke_authorized(
        capability=capability,
        tool_name="payments.refund",
        payload={"amount": 100},
        context=context(),
    )
    assert result.success is False
    assert "requires approval" in result.error
    assert calls == []


def test_sensitive_tool_rejects_approval_for_another_tool():
    registry, calls, capability = setup()
    result = ToolInvoker(registry).invoke_authorized(
        capability=capability,
        tool_name="payments.refund",
        payload={"amount": 100},
        context=context(
            tool_approval={
                "tool_name": "payments.capture",
                "approved": True,
            }
        ),
    )
    assert result.success is False
    assert calls == []


def test_sensitive_tool_executes_with_explicit_matching_approval():
    registry, calls, capability = setup()
    result = ToolInvoker(registry).invoke_authorized(
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
    assert result.success is True
    assert calls == [{"amount": 100}]


def test_capability_mismatch_still_denies_even_with_approval():
    registry, calls, capability = setup()
    wrong = ToolExecutionContext(
        tenant_id="tenant-a",
        agent_name="payments-agent",
        capability_name="other_capability",
        metadata={
            "tool_approval": {
                "tool_name": "payments.refund",
                "approved": True,
            }
        },
    )
    result = ToolInvoker(registry).invoke_authorized(
        capability=capability,
        tool_name="payments.refund",
        payload={},
        context=wrong,
    )
    assert result.success is False
    assert calls == []
