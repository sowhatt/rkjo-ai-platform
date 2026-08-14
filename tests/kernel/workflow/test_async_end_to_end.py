
import os
import threading
import time

import psycopg
import pytest

from rkjo_kernel.agents.base_agent import BaseAgent
from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.registry.descriptor import AgentDescriptor, AgentStatus
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.runtime.agent_runtime import AgentRuntime
from rkjo_kernel.runtime.result_publisher import AgentResultPublisher
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.workflow.async_dispatch import AsyncWorkflowDispatcher
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.models.workflow_definition import WorkflowDefinition
from rkjo_kernel.workflow.models.workflow_status import WorkflowStatus
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep
from rkjo_kernel.workflow.repository.postgres import PostgreSQLWorkflowRepository
from rkjo_kernel.workflow.result_handler import WorkflowResultHandler


DATABASE_URL = os.getenv(
    "RKJO_TEST_DATABASE_URL",
    "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
)

AGENT_QUEUE = "rkjo.test.e2e.weather"
RESULT_QUEUE = "rkjo.test.e2e.results"


class WeatherAgent(BaseAgent):
    def process(self, message):
        result = {
            "temperature": 31,
            "provider": "test",
        }

        # The RabbitMQ BlockingConnection consumer must be
        # stopped from the same thread that owns it.
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


def make_registry_service():
    registry = AgentRegistry()

    service = RegistryService(
        registry=registry
    )

    service.register_agent(
        AgentDescriptor(
            name="weather.agent",
            display_name="Weather Agent",
            product="ADIP",
            queue_name=AGENT_QUEUE,
            status=AgentStatus.AVAILABLE,
        )
    )

    return service


def make_definition():
    return WorkflowDefinition(
        workflow_id="workflow-e2e",
        name="Workflow Async E2E",
        steps=[
            WorkflowStep(
                step_id="weather",
                name="Weather Analysis",
                agent_name="weather.agent",
                position=0,
            )
        ],
    )


def test_async_workflow_end_to_end(repository):
    workflow_bus = RabbitMQEventBus()
    agent_bus = RabbitMQEventBus()
    result_bus = RabbitMQEventBus()

    engine = WorkflowEngine(
        repository=repository
    )

    execution = engine.create_execution(
        make_definition(),
        execution_id="e2e-001",
        input_data={
            "parcel_id": "P-100",
        },
    )

    engine.start(execution)
    step = engine.start_next_step(execution)

    assert step is not None

    agent = WeatherAgent(
        agent_name="weather.agent",
        queue_name=AGENT_QUEUE,
        event_bus=agent_bus,
    )

    result_publisher = AgentResultPublisher(
        event_bus=agent_bus,
        source=agent.agent_name,
    )

    runtime = AgentRuntime(
        agent=agent,
        event_bus=agent_bus,
        registry_service=make_registry_service(),
        result_publisher=result_publisher,
    )

    result_handler = WorkflowResultHandler(
        engine=engine
    )

    received_results = []

    def result_callback(message):
        received_results.append(message)
        result_handler.handle(message)
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
        correlation_id="corr-e2e-001",
        reply_queue=RESULT_QUEUE,
    )

    result_thread.join(timeout=5)

    try:
        assert len(received_results) == 1

        restored = repository.get(
            execution.execution_id
        )

        assert restored is not None

        assert restored.status == (
            WorkflowStatus.COMPLETED
        )

        assert restored.current_step_id is None

        assert restored.context.outputs == {
            "weather": {
                "temperature": 31,
                "provider": "test",
            }
        }

    finally:
        if result_bus.connection.is_open:
            result_bus.close()

        if workflow_bus.connection.is_open:
            workflow_bus.close()

        runtime_thread.join(timeout=5)

        assert not runtime_thread.is_alive()

        if agent_bus.connection.is_open:
            agent_bus.close()
