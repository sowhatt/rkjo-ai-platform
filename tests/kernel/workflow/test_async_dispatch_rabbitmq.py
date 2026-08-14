
import threading
import time

from rkjo_kernel.events.rabbitmq_event_bus import (
    RabbitMQEventBus,
)
from rkjo_kernel.workflow.async_dispatch import (
    AsyncWorkflowDispatcher,
)
from rkjo_kernel.workflow.models.workflow_context import (
    WorkflowContext,
)
from rkjo_kernel.workflow.models.workflow_step import (
    WorkflowStep,
)


QUEUE_NAME = "rkjo.test.workflow.async"


def test_async_dispatch_round_trip_through_rabbitmq():
    publisher_bus = RabbitMQEventBus()
    consumer_bus = RabbitMQEventBus()

    received = []

    step = WorkflowStep(
        step_id="weather",
        name="Weather Analysis",
        capability_name="weather.analysis",
    )

    dispatcher = AsyncWorkflowDispatcher(
        event_bus=publisher_bus
    )

    def callback(message):
        received.append(message)

        # Stop BlockingConnection consumption
        # once the expected message is received.
        consumer_bus.channel.stop_consuming()

    consumer_thread = threading.Thread(
        target=consumer_bus.consume_agent_messages,
        kwargs={
            "queue_name": QUEUE_NAME,
            "callback": callback,
        },
        daemon=True,
    )

    consumer_thread.start()

    # Give the RabbitMQ consumer enough time
    # to declare its queue and start consuming.
    time.sleep(0.2)

    result = dispatcher.dispatch(
        step=step,
        context=WorkflowContext(
            input_data={
                "parcel_id": "P-100",
            },
            metadata={
                "product": "ADIP",
            },
        ),
        queue_name=QUEUE_NAME,
        execution_id="execution-rabbit-001",
        correlation_id="corr-rabbit-001",
    )

    consumer_thread.join(timeout=5)

    try:
        assert len(received) == 1

        message = received[0]

        assert message.message_id == result.message_id
        assert message.correlation_id == (
            "corr-rabbit-001"
        )
        assert message.message_type == (
            "workflow.step.execute"
        )

        assert message.metadata[
            "workflow_execution_id"
        ] == "execution-rabbit-001"

        assert message.metadata[
            "workflow_step_id"
        ] == "weather"

        assert message.metadata[
            "capability_name"
        ] == "weather.analysis"

        assert message.payload[
            "input_data"
        ] == {
            "parcel_id": "P-100"
        }

    finally:
        if consumer_bus.connection.is_open:
            consumer_bus.close()

        if publisher_bus.connection.is_open:
            publisher_bus.close()
