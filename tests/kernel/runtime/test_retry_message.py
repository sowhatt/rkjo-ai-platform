from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.runtime.retry_message import (
    build_retry_message,
)


def make_message():
    return AgentMessage(
        message_id="message-001",
        correlation_id="corr-001",
        source="rkjo.workflow",
        target="weather.agent",
        message_type="workflow.step.execute",
        payload={
            "parcel_id": "P-100",
        },
        metadata={
            "workflow_execution_id": "exec-001",
            "workflow_step_id": "weather",
            "attempt": 1,
        },
    )


def test_retry_message_has_new_message_id():
    original = make_message()

    retry = build_retry_message(
        original_message=original
    )

    assert retry.message_id != original.message_id


def test_retry_message_keeps_correlation_id():
    original = make_message()

    retry = build_retry_message(
        original_message=original
    )

    assert retry.correlation_id == (
        original.correlation_id
    )


def test_retry_message_increments_attempt():
    original = make_message()

    retry = build_retry_message(
        original_message=original
    )

    assert retry.metadata["attempt"] == 2

    assert retry.metadata[
        "retry_of_message_id"
    ] == original.message_id


def test_retry_message_preserves_payload():
    original = make_message()

    retry = build_retry_message(
        original_message=original
    )

    assert retry.payload == original.payload
    assert retry.payload is not original.payload
