from rkjo_kernel.workflow.async_dispatch import (
    AsyncWorkflowDispatcher,
)
from rkjo_kernel.workflow.models.workflow_context import (
    WorkflowContext,
)
from rkjo_kernel.workflow.models.workflow_step import (
    WorkflowStep,
)


class RecordingEventBus:
    def __init__(self):
        self.published = []

    def publish_agent_message(
        self,
        *,
        queue_name,
        message,
    ):
        self.published.append(
            (queue_name, message)
        )


def make_step():
    return WorkflowStep(
        step_id="diagnostic",
        name="Diagnostic",
        capability_name="education.diagnostic",
    )


def make_context():
    return WorkflowContext(
        input_data={
            "student_id": "student-001",
        },
        variables={
            "level": "CE1",
        },
        metadata={
            "tenant_id": "tenant-001",
        },
    )


def test_prepare_builds_message_without_publishing():
    event_bus = RecordingEventBus()

    dispatcher = AsyncWorkflowDispatcher(
        event_bus=event_bus,
    )

    queue_name, message = dispatcher.prepare(
        step=make_step(),
        context=make_context(),
        queue_name="diagnostic.agent",
        execution_id="execution-001",
        correlation_id="corr-001",
        reply_queue="rkjo.workflow.results",
        target_agent_name="diagnostic.agent",
    )

    assert queue_name == "diagnostic.agent"

    assert message.target == "diagnostic.agent"
    assert message.source == "rkjo.workflow"
    assert message.message_type == (
        "workflow.step.execute"
    )
    assert message.correlation_id == "corr-001"

    assert message.metadata[
        "workflow_execution_id"
    ] == "execution-001"

    assert message.metadata[
        "workflow_step_id"
    ] == "diagnostic"

    assert message.metadata[
        "capability_name"
    ] == "education.diagnostic"

    assert message.metadata[
        "reply_queue"
    ] == "rkjo.workflow.results"

    assert event_bus.published == []


def test_dispatch_still_publishes_prepared_message():
    event_bus = RecordingEventBus()

    dispatcher = AsyncWorkflowDispatcher(
        event_bus=event_bus,
    )

    result = dispatcher.dispatch(
        step=make_step(),
        context=make_context(),
        queue_name="diagnostic.agent",
        execution_id="execution-001",
        correlation_id="corr-001",
        reply_queue="rkjo.workflow.results",
        target_agent_name="diagnostic.agent",
    )

    assert len(event_bus.published) == 1

    queue_name, message = (
        event_bus.published[0]
    )

    assert queue_name == "diagnostic.agent"
    assert message.message_id == result.message_id
    assert (
        message.correlation_id
        == result.correlation_id
    )
    assert message.target == "diagnostic.agent"
