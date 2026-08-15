
import os
import threading
import time

import psycopg
import pytest

from rkjo_kernel.agents.base_agent import BaseAgent
from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.runtime.agent_runtime import AgentRuntime
from rkjo_kernel.runtime.dead_letter_publisher import (
    DeadLetterPublisher,
)
from rkjo_kernel.runtime.result_publisher import (
    AgentResultPublisher,
)
from rkjo_kernel.runtime.retry_policy import RetryPolicy
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.workflow.async_dispatch import AsyncWorkflowDispatcher
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.models.workflow_definition import (
    WorkflowDefinition,
)
from rkjo_kernel.workflow.models.workflow_status import (
    WorkflowStatus,
)
from rkjo_kernel.workflow.models.workflow_step import (
    WorkflowStep,
)
from rkjo_kernel.workflow.repository.postgres import (
    PostgreSQLWorkflowRepository,
)
from rkjo_kernel.workflow.result_handler import (
    WorkflowResultHandler,
)


DATABASE_URL = os.getenv(
    "RKJO_TEST_DATABASE_URL",
    "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
)

AGENT_QUEUE = "rkjo.test.dlq.e2e.agent"
RESULT_QUEUE = "rkjo.test.dlq.e2e.results"
DLQ_QUEUE = "rkjo.test.dlq.e2e.dlq"


class AlwaysTimeoutAgent(BaseAgent):
    def process(self, message):
        raise TimeoutError(
            "provider timeout"
        )


@pytest.fixture
def repository():
    repo = PostgreSQLWorkflowRepository(
        DATABASE_URL
    )

    repo.initialize_schema()

    yield repo

    with psycopg.connect(
        DATABASE_URL
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM workflow_executions;"
            )


def purge_queue(queue_name):
    bus = RabbitMQEventBus()

    try:
        bus.channel.queue_declare(
            queue=queue_name,
            durable=True,
        )
        bus.channel.queue_purge(
            queue=queue_name,
        )
    finally:
        bus.close()


@pytest.fixture(autouse=True)
def clean_rabbitmq_queues():
    for queue in (
        AGENT_QUEUE,
        RESULT_QUEUE,
        DLQ_QUEUE,
    ):
        purge_queue(queue)

    yield

    for queue in (
        AGENT_QUEUE,
        RESULT_QUEUE,
        DLQ_QUEUE,
    ):
        purge_queue(queue)


def make_registry_service():
    registry = AgentRegistry()

    service = RegistryService(
        registry=registry
    )

    service.register_agent(
        AgentDescriptor(
            name="timeout.agent",
            display_name="Timeout Agent",
            product="ADIP",
            queue_name=AGENT_QUEUE,
            status=AgentStatus.AVAILABLE,
        )
    )

    return service


def make_definition():
    return WorkflowDefinition(
        workflow_id="workflow-dlq-e2e",
        name="DLQ E2E Workflow",
        steps=[
            WorkflowStep(
                step_id="weather",
                name="Weather",
                agent_name="timeout.agent",
            )
        ],
    )


def consume_one_dlq_message():
    bus = RabbitMQEventBus()
    received = []

    try:
        bus.channel.queue_declare(
            queue=DLQ_QUEUE,
            durable=True,
        )

        method, properties, body = (
            bus.channel.basic_get(
                queue=DLQ_QUEUE,
                auto_ack=False,
            )
        )

        if method is None:
            return None

        from rkjo_kernel.messages.agent_message import AgentMessage

        message = AgentMessage.model_validate_json(
            body
        )

        bus.channel.basic_ack(
            delivery_tag=method.delivery_tag,
        )

        received.append(message)

        return received[0]

    finally:
        bus.close()


def test_retry_exhaustion_moves_message_to_dlq_and_fails_workflow(
    repository,
):
    workflow_bus = RabbitMQEventBus()
    agent_bus = RabbitMQEventBus()
    result_bus = RabbitMQEventBus()

    engine = WorkflowEngine(
        repository=repository
    )

    execution = engine.create_execution(
        make_definition(),
        execution_id="dlq-e2e-001",
    )

    engine.start(execution)

    step = engine.start_next_step(
        execution
    )

    assert step is not None

    agent = AlwaysTimeoutAgent(
        agent_name="timeout.agent",
        queue_name=AGENT_QUEUE,
        event_bus=agent_bus,
    )

    runtime = AgentRuntime(
        agent=agent,
        event_bus=agent_bus,
        registry_service=make_registry_service(),
        result_publisher=AgentResultPublisher(
            event_bus=agent_bus,
            source=agent.agent_name,
        ),
        retry_policy=RetryPolicy(
            max_attempts=3,
            base_delay_seconds=0,
        ),
        dead_letter_publisher=DeadLetterPublisher(
            event_bus=agent_bus,
            queue_name=DLQ_QUEUE,
        ),
    )

    result_handler = WorkflowResultHandler(
        engine=engine
    )

    received_results = []

    def result_callback(message):
        received_results.append(message)

        result_handler.handle(
            message
        )

        result_bus.channel.stop_consuming()

    result_thread = threading.Thread(
        target=result_bus.consume_agent_messages,
        kwargs={
            "queue_name": RESULT_QUEUE,
            "callback": result_callback,
        },
        daemon=True,
    )

    runtime_thread = threading.Thread(
        target=runtime.start,
        daemon=True,
    )

    result_thread.start()
    runtime_thread.start()

    time.sleep(0.3)

    dispatcher = AsyncWorkflowDispatcher(
        event_bus=workflow_bus
    )

    dispatcher.dispatch(
        step=step,
        context=execution.context,
        queue_name=AGENT_QUEUE,
        execution_id=execution.execution_id,
        correlation_id="corr-dlq-e2e-001",
        reply_queue=RESULT_QUEUE,
    )

    result_thread.join(
        timeout=5
    )

    # runtime continues listening after terminal failure,
    # so stop it safely from its own connection thread context
    # by scheduling stop_consuming on the connection.
    if agent_bus.connection.is_open:
        agent_bus.connection.add_callback_threadsafe(
            agent_bus.channel.stop_consuming
        )

    runtime_thread.join(
        timeout=5
    )

    try:
        assert not result_thread.is_alive()
        assert not runtime_thread.is_alive()

        assert len(received_results) == 1

        failure_result = (
            received_results[0]
        )

        assert failure_result.payload[
            "success"
        ] is False

        assert (
            failure_result.payload["error"]
            == "provider timeout"
        )

        restored = repository.get(
            execution.execution_id
        )

        assert restored is not None

        assert restored.status == (
            WorkflowStatus.FAILED
        )

        assert restored.error == (
            "provider timeout"
        )

        dead_letter = (
            consume_one_dlq_message()
        )

        assert dead_letter is not None

        assert dead_letter.message_type == (
            "workflow.step.dead_letter"
        )

        assert dead_letter.correlation_id == (
            "corr-dlq-e2e-001"
        )

        assert dead_letter.payload[
            "reason"
        ] == "max_attempts_reached"

        assert dead_letter.metadata[
            "attempt"
        ] == 3

    finally:
        if result_bus.connection.is_open:
            result_bus.close()

        if workflow_bus.connection.is_open:
            workflow_bus.close()

        if agent_bus.connection.is_open:
            agent_bus.close()
