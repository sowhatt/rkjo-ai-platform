import os

import psycopg
import pytest

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.workflow.agent_routing import WorkflowAgentRouter
from rkjo_kernel.workflow.async_dispatch import AsyncWorkflowDispatcher
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.models.workflow_definition import (
    WorkflowDefinition,
)
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep
from rkjo_kernel.workflow.outbox_publisher import OutboxPublisher
from rkjo_kernel.workflow.postgres_unit_of_work import (
    PostgreSQLWorkflowUnitOfWork,
)
from rkjo_kernel.workflow.transactional_result_handler import (
    TransactionalWorkflowResultHandler,
)


DATABASE_URL = os.getenv(
    "RKJO_TEST_DATABASE_URL",
    "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
)


class RecordingEventBus(EventBus):
    def __init__(self) -> None:
        self.published = []

    def publish(self, queue_name, message):
        pass

    def consume(self, queue_name, callback):
        pass

    def publish_agent_message(
        self,
        queue_name,
        message,
    ):
        self.published.append(
            (queue_name, message)
        )

    def consume_agent_messages(
        self,
        queue_name,
        callback,
    ):
        pass

    def close(self):
        pass


@pytest.fixture
def postgres_database():
    bootstrap = PostgreSQLWorkflowUnitOfWork(
        DATABASE_URL
    )
    bootstrap.initialize_schema()

    def clean():
        with psycopg.connect(
            DATABASE_URL
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM workflow_outbox;"
                )
                cursor.execute(
                    "DELETE FROM workflow_inbox;"
                )
                cursor.execute(
                    "DELETE FROM workflow_executions;"
                )

    clean()
    yield
    clean()


def uow_factory():
    return PostgreSQLWorkflowUnitOfWork(
        DATABASE_URL
    )


def make_definition():
    return WorkflowDefinition(
        workflow_id="postgres-async-flow",
        name="PostgreSQL Async Flow",
        steps=[
            WorkflowStep(
                step_id="step-1",
                name="Diagnostic",
                agent_name="agent.one",
                position=0,
            ),
            WorkflowStep(
                step_id="step-2",
                name="Tutor",
                agent_name="agent.two",
                position=1,
            ),
        ],
    )


def test_postgres_result_to_outbox_to_publication(
    postgres_database,
):
    # -------------------------------------------------
    # 1. Persist a real running workflow in PostgreSQL.
    # -------------------------------------------------
    with uow_factory() as uow:
        engine = WorkflowEngine(
            repository=uow.workflows
        )

        execution = engine.create_execution(
            make_definition(),
            execution_id="postgres-async-001",
        )

        engine.start(execution)
        engine.start_next_step(execution)

        assert execution.current_step_id == "step-1"

        uow.commit()

    # -------------------------------------------------
    # 2. Configure routing of the second agent.
    # -------------------------------------------------
    registry = AgentRegistry()
    registry_service = RegistryService(
        registry=registry
    )

    registry_service.register_agent(
        AgentDescriptor(
            name="agent.two",
            display_name="Agent Two",
            product="RKJO",
            queue_name="agent.two.queue",
            status=AgentStatus.AVAILABLE,
        )
    )

    bus = RecordingEventBus()

    handler = TransactionalWorkflowResultHandler(
        uow_factory=uow_factory,
        router=WorkflowAgentRouter(
            registry_service=registry_service
        ),
        dispatcher=AsyncWorkflowDispatcher(
            event_bus=bus
        ),
        reply_queue="rkjo.workflow.results",
    )

    result_message = AgentMessage(
        message_id="postgres-result-001",
        correlation_id="postgres-corr-001",
        source="agent.one",
        target="rkjo.workflow",
        message_type="workflow.step.result",
        payload={
            "success": True,
            "result": {
                "level": "beginner",
            },
        },
        metadata={
            "workflow_execution_id": (
                "postgres-async-001"
            ),
            "workflow_step_id": "step-1",
        },
    )

    # -------------------------------------------------
    # 3. Process result transactionally.
    # -------------------------------------------------
    handler.handle(result_message)

    # Handler must NOT publish directly.
    assert bus.published == []

    # -------------------------------------------------
    # 4. Verify the atomic PostgreSQL state.
    # -------------------------------------------------
    with uow_factory() as verification:
        restored = verification.workflows.get(
            "postgres-async-001"
        )

        assert restored is not None

        assert (
            restored.current_step_id
            == "step-2"
        )

        assert restored.context.outputs[
            "step-1"
        ] == {
            "level": "beginner",
        }

        assert verification.inbox.contains(
            "postgres-result-001"
        )

        pending = verification.outbox.pending()

        assert len(pending) == 1

        outbox_message = pending[0]

        assert (
            outbox_message.queue_name
            == "agent.two.queue"
        )

        assert (
            outbox_message.message.target
            == "agent.two"
        )

        assert (
            outbox_message.message.correlation_id
            == "postgres-corr-001"
        )

        assert (
            outbox_message.message.metadata[
                "workflow_execution_id"
            ]
            == "postgres-async-001"
        )

        assert (
            outbox_message.message.metadata[
                "workflow_step_id"
            ]
            == "step-2"
        )

    # -------------------------------------------------
    # 5. Publish committed outbox.
    # -------------------------------------------------
    publisher = OutboxPublisher(
        event_bus=bus,
        uow_factory=uow_factory,
    )

    published_count = publisher.publish_pending()

    assert published_count == 1
    assert len(bus.published) == 1

    queue_name, published_message = (
        bus.published[0]
    )

    assert queue_name == "agent.two.queue"
    assert published_message.target == "agent.two"

    assert (
        published_message.correlation_id
        == "postgres-corr-001"
    )

    # -------------------------------------------------
    # 6. Publication acknowledgment persisted.
    # -------------------------------------------------
    with uow_factory() as verification:
        assert verification.outbox.pending() == []

        assert verification.inbox.contains(
            "postgres-result-001"
        )

        restored = verification.workflows.get(
            "postgres-async-001"
        )

        assert restored is not None
        assert restored.current_step_id == "step-2"


class FailingOnceEventBus(RecordingEventBus):
    def __init__(self):
        super().__init__()
        self.failures_remaining = 1

    def publish_agent_message(
        self,
        queue_name,
        message,
    ):
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise RuntimeError(
                "simulated broker failure"
            )

        super().publish_agent_message(
            queue_name,
            message,
        )


def test_outbox_survives_broker_failure_and_retries(
    postgres_database,
):
    # Persist an outbox message through the normal
    # transactional workflow result path.
    with uow_factory() as uow:
        engine = WorkflowEngine(
            repository=uow.workflows
        )

        execution = engine.create_execution(
            make_definition(),
            execution_id="postgres-retry-001",
        )

        engine.start(execution)
        engine.start_next_step(execution)

        uow.commit()

    registry = AgentRegistry()
    registry_service = RegistryService(
        registry=registry
    )

    registry_service.register_agent(
        AgentDescriptor(
            name="agent.two",
            display_name="Agent Two",
            product="RKJO",
            queue_name="agent.two.queue",
            status=AgentStatus.AVAILABLE,
        )
    )

    preparation_bus = RecordingEventBus()

    handler = TransactionalWorkflowResultHandler(
        uow_factory=uow_factory,
        router=WorkflowAgentRouter(
            registry_service=registry_service
        ),
        dispatcher=AsyncWorkflowDispatcher(
            event_bus=preparation_bus
        ),
        reply_queue="rkjo.workflow.results",
    )

    result_message = AgentMessage(
        message_id="postgres-retry-result-001",
        correlation_id="postgres-retry-corr-001",
        source="agent.one",
        target="rkjo.workflow",
        message_type="workflow.step.result",
        payload={
            "success": True,
            "result": {
                "value": "ready",
            },
        },
        metadata={
            "workflow_execution_id": (
                "postgres-retry-001"
            ),
            "workflow_step_id": "step-1",
        },
    )

    handler.handle(result_message)

    with uow_factory() as verification:
        pending = verification.outbox.pending()
        assert len(pending) == 1

        original_outbox_id = (
            pending[0].outbox_id
        )

    # First publication attempt fails.
    failing_bus = FailingOnceEventBus()

    publisher = OutboxPublisher(
        event_bus=failing_bus,
        uow_factory=uow_factory,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated broker failure",
    ):
        publisher.publish_pending()

    # The outbox record must still be pending.
    with uow_factory() as verification:
        pending = verification.outbox.pending()

        assert len(pending) == 1
        assert (
            pending[0].outbox_id
            == original_outbox_id
        )

    assert failing_bus.published == []

    # Second attempt succeeds.
    published_count = publisher.publish_pending()

    assert published_count == 1
    assert len(failing_bus.published) == 1

    # The durable outbox is now acknowledged.
    with uow_factory() as verification:
        assert verification.outbox.pending() == []
