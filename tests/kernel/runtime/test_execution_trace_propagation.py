from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.runtime.dead_letter_publisher import DeadLetterPublisher
from rkjo_kernel.runtime.result_publisher import AgentResultPublisher
from rkjo_kernel.runtime.retry_message import build_retry_message


class FakeEventBus(EventBus):
    def __init__(self):
        self.messages = []

    def publish(self, queue_name, message):
        pass

    def consume(self, queue_name, callback):
        pass

    def publish_agent_message(self, queue_name, message):
        self.messages.append((queue_name, message))

    def consume_agent_messages(self, queue_name, callback):
        pass

    def close(self):
        pass


def make_request() -> AgentMessage:
    return AgentMessage(
        message_id="request-001",
        correlation_id="corr-001",
        source="rkjo.workflow",
        target="education.tutor",
        message_type="workflow.step.execute",
        payload={"topic": "fractions"},
        metadata={
            "reply_queue": "workflow.results",
            "trace_id": "trace-001",
            "mission_id": "mission-001",
            "workflow_execution_id": "exec-001",
            "workflow_step_id": "teach",
            "capability_name": "education.explain",
            "tenant_id": "tenant-001",
            "user_id": "user-001",
            "attempt": 1,
        },
    )


def test_success_result_preserves_transverse_trace_metadata():
    bus = FakeEventBus()
    publisher = AgentResultPublisher(
        event_bus=bus,
        source="education.tutor",
    )

    response = publisher.publish_success(
        request=make_request(),
        result={"ok": True},
    )

    assert response is not None
    assert response.correlation_id == "corr-001"
    assert response.metadata["trace_id"] == "trace-001"
    assert response.metadata["mission_id"] == "mission-001"
    assert response.metadata["workflow_execution_id"] == "exec-001"
    assert response.metadata["workflow_step_id"] == "teach"
    assert response.metadata["capability_name"] == "education.explain"
    assert response.metadata["tenant_id"] == "tenant-001"
    assert response.metadata["user_id"] == "user-001"
    assert "reply_queue" not in response.metadata


def test_failure_result_preserves_mission_and_trace():
    bus = FakeEventBus()
    publisher = AgentResultPublisher(
        event_bus=bus,
        source="education.tutor",
    )

    response = publisher.publish_failure(
        request=make_request(),
        error=RuntimeError("boom"),
    )

    assert response is not None
    assert response.metadata["trace_id"] == "trace-001"
    assert response.metadata["mission_id"] == "mission-001"
    assert response.metadata["workflow_execution_id"] == "exec-001"


def test_retry_preserves_same_trace_and_mission_with_new_message_id():
    original = make_request()

    retry = build_retry_message(original_message=original)

    assert retry.message_id != original.message_id
    assert retry.correlation_id == original.correlation_id
    assert retry.metadata["trace_id"] == "trace-001"
    assert retry.metadata["mission_id"] == "mission-001"
    assert retry.metadata["workflow_execution_id"] == "exec-001"
    assert retry.metadata["workflow_step_id"] == "teach"
    assert retry.metadata["capability_name"] == "education.explain"
    assert retry.metadata["attempt"] == 2
    assert retry.metadata["retry_of_message_id"] == "request-001"


def test_dead_letter_preserves_same_trace_and_mission():
    bus = FakeEventBus()
    publisher = DeadLetterPublisher(
        event_bus=bus,
        queue_name="rkjo.dlq",
    )

    dead_letter = publisher.publish(
        original_message=make_request(),
        reason="max_attempts_reached",
    )

    assert dead_letter.correlation_id == "corr-001"
    assert dead_letter.metadata["trace_id"] == "trace-001"
    assert dead_letter.metadata["mission_id"] == "mission-001"
    assert dead_letter.metadata["workflow_execution_id"] == "exec-001"
    assert dead_letter.metadata["workflow_step_id"] == "teach"
    assert dead_letter.metadata["capability_name"] == "education.explain"
    assert dead_letter.metadata["tenant_id"] == "tenant-001"
    assert dead_letter.metadata["user_id"] == "user-001"
