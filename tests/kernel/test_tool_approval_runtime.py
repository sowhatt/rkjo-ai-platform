import pytest

from rkjo_kernel.tools.approval import (
    ApprovalStatus,
    InMemoryToolApprovalStore,
    ToolApprovalService,
)


def test_approval_lifecycle_is_tenant_and_execution_scoped():
    service = ToolApprovalService(InMemoryToolApprovalStore())
    request = service.request(
        tenant_id="tenant-a",
        tool_name="payments.refund",
        mission_id="Mission-1",
        trace_id="Trace-1",
        requested_by="agent-a",
    )
    assert request.status is ApprovalStatus.PENDING
    assert service.authorize(
        approval_id=request.approval_id,
        tenant_id="tenant-a",
        tool_name="payments.refund",
        mission_id="Mission-1",
        trace_id="Trace-1",
    ) is False

    approved = service.decide(
        approval_id=request.approval_id,
        tenant_id="tenant-a",
        approved=True,
        decided_by="human@example.com",
    )
    assert approved.status is ApprovalStatus.APPROVED
    assert approved.decided_at is not None

    assert service.authorize(
        approval_id=request.approval_id,
        tenant_id="tenant-a",
        tool_name="payments.refund",
        mission_id="Mission-1",
        trace_id="Trace-1",
    ) is True
    assert service.authorize(
        approval_id=request.approval_id,
        tenant_id="tenant-b",
        tool_name="payments.refund",
        mission_id="Mission-1",
        trace_id="Trace-1",
    ) is False
    assert service.authorize(
        approval_id=request.approval_id,
        tenant_id="tenant-a",
        tool_name="payments.refund",
        mission_id="Other-Mission",
        trace_id="Trace-1",
    ) is False


def test_rejected_approval_never_authorizes():
    service = ToolApprovalService(InMemoryToolApprovalStore())
    request = service.request(
        tenant_id="tenant-a",
        tool_name="payments.refund",
        mission_id="m1",
        trace_id="t1",
    )
    rejected = service.decide(
        approval_id=request.approval_id,
        tenant_id="tenant-a",
        approved=False,
        decided_by="reviewer",
        reason="amount too high",
    )
    assert rejected.status is ApprovalStatus.REJECTED
    assert service.authorize(
        approval_id=request.approval_id,
        tenant_id="tenant-a",
        tool_name="payments.refund",
        mission_id="m1",
        trace_id="t1",
    ) is False


def test_decision_is_immutable():
    service = ToolApprovalService(InMemoryToolApprovalStore())
    request = service.request(
        tenant_id="tenant-a",
        tool_name="payments.refund",
    )
    service.decide(
        approval_id=request.approval_id,
        tenant_id="tenant-a",
        approved=True,
        decided_by="reviewer",
    )
    with pytest.raises(ValueError, match="already been decided"):
        service.decide(
            approval_id=request.approval_id,
            tenant_id="tenant-a",
            approved=False,
            decided_by="other-reviewer",
        )
