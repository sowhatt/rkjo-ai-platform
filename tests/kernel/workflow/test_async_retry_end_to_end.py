
import os
import threading
import time

import psycopg
import pika
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

AGENT_QUEUE = "rkjo.test.retry.e2e.agent"
RESULT_QUEUE = "rkjo.test.retry.e2e.results"
DLQ_QUEUE = "rkjo.test.retry.e2e.dlq"


class RetryThenSuccessAgent(BaseAgent):
    def process(self, message):
        attempt = int(
            message.metadata.get(
                "attempt",
                1,
            )
        )

        if attempt == 1:
            raise TimeoutError(
                "temporary provider timeout"
            )

        result = {
            "temperature": 31,
            "attempt": attempt,
        }

        # Stop consumer from the thread that owns
        # the BlockingConnection once retry succeeds.
        self.event_bus.channel.stop_consuming()

        return result


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
            name="retry.agent",
            display_name="Retry Agent",
            product="ADIP",
            queue_name=AGENT_QUEUE,
            status=AgentStatus.AVAILABLE,
        )
    )

    return service


def make_definition():
    return WorkflowDefinition(
        workflow_id="workflow-retry-e2e",
        name="Retry E2E Workflow",
        steps=[
            WorkflowStep(
                step_id="weather",
                name="Weather",
                agent_name="retry.agent",
            )
        ],
    )


def queue_message_count(
    queue_name,
):
    bus = RabbitMQEventBus()

    try:
        result = bus.channel.queue_declare(
            queue=queue_name,
            durable=True,
            passive=True,
        )

        return result.method.message_count
    finally:
        bus.close()


def test_retry_then_success_end_to_end(
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
        execution_id="retry-e2e-001",
    )

    engine.start(execution)

    step = engine.start_next_step(
        execution
    )

    assert step is not None

    agent = RetryThenSuccessAgent(
        agent_name="retry.agent",
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
        received_results.append(
            message
        )

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
        correlation_id="corr-retry-e2e-001",
        reply_queue=RESULT_QUEUE,
    )

    result_thread.join(
        timeout=5
    )

    runtime_thread.join(
        timeout=5
    )

    try:
        assert not result_thread.is_alive()
        assert not runtime_thread.is_alive()

        assert len(
            received_results
        ) == 1

        result_message = (
            received_results[0]
        )

        assert result_message.payload[
            "success"
        ] is True

        assert result_message.payload[
            "result"
        ] == {
            "temperature": 31,
            "attempt": 2,
        }

        restored = repository.get(
            execution.execution_id
        )

        assert restored is not None

        assert restored.status == (
            WorkflowStatus.COMPLETED
        )

        assert restored.context.outputs == {
            "weather": {
                "temperature": 31,
                "attempt": 2,
            }
        }

        assert queue_message_count(
            DLQ_QUEUE
        ) == 0

    finally:
        if result_bus.connection.is_open:
            result_bus.close()

        if workflow_bus.connection.is_open:
            workflow_bus.close()

        if agent_bus.connection.is_open:
            agent_bus.close()
