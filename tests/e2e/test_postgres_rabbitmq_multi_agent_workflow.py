import os
import threading
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import psycopg

from rkjo_kernel.agents.base_agent import BaseAgent
from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.runtime.agent_runtime import AgentRuntime
from rkjo_kernel.runtime.result_publisher import AgentResultPublisher
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.workflow.agent_routing import WorkflowAgentRouter
from rkjo_kernel.workflow.async_coordinator import AsyncWorkflowCoordinator
from rkjo_kernel.workflow.async_dispatch import AsyncWorkflowDispatcher
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.models.workflow_definition import (
    WorkflowDefinition,
)
from rkjo_kernel.workflow.models.workflow_status import WorkflowStatus
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep
from rkjo_kernel.workflow.outbox import OutboxMessage
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


class DiagnosticAgent(BaseAgent):
    def process(
        self,
        message: AgentMessage,
    ) -> dict[str, Any]:
        return {
            "student_level": "beginner",
            "difficulty": "addition",
        }


class TutorAgent(BaseAgent):
    def process(
        self,
        message: AgentMessage,
    ) -> dict[str, Any]:
        outputs = message.payload["outputs"]

        assert outputs["diagnostic"] == {
            "student_level": "beginner",
            "difficulty": "addition",
        }

        return {
            "lesson": "addition-with-carry",
            "explanation": "27 + 18 = 45",
        }


class ExerciseAgent(BaseAgent):
    def process(
        self,
        message: AgentMessage,
    ) -> dict[str, Any]:
        outputs = message.payload["outputs"]

        assert outputs["diagnostic"] == {
            "student_level": "beginner",
            "difficulty": "addition",
        }

        assert outputs["tutoring"] == {
            "lesson": "addition-with-carry",
            "explanation": "27 + 18 = 45",
        }

        return {
            "exercise": "34 + 29",
            "expected_answer": 63,
        }


def uow_factory():
    return PostgreSQLWorkflowUnitOfWork(
        DATABASE_URL
    )


def register_agent(
    service: RegistryService,
    *,
    name: str,
    queue_name: str,
) -> None:
    service.register_agent(
        AgentDescriptor(
            name=name,
            display_name=name,
            product="RKJO Education",
            queue_name=queue_name,
            status=AgentStatus.AVAILABLE,
        )
    )


def clean_database() -> None:
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


def test_real_postgres_rabbitmq_three_agent_workflow():
    bootstrap = PostgreSQLWorkflowUnitOfWork(
        DATABASE_URL
    )
    bootstrap.initialize_schema()
    clean_database()

    run_id = uuid4().hex[:10]

    execution_id = (
        f"education-rabbit-postgres-{run_id}"
    )

    correlation_id = (
        f"corr-rabbit-postgres-{run_id}"
    )

    result_queue = (
        f"rkjo.workflow.results.{run_id}"
    )

    diagnostic_queue = (
        f"education.diagnostic.{run_id}"
    )

    tutor_queue = (
        f"education.tutor.{run_id}"
    )

    exercise_queue = (
        f"education.exercise.{run_id}"
    )

    diagnostic_name = (
        f"education.diagnostic.agent.{run_id}"
    )

    tutor_name = (
        f"education.tutor.agent.{run_id}"
    )

    exercise_name = (
        f"education.exercise.agent.{run_id}"
    )

    registry = AgentRegistry()

    registry_service = RegistryService(
        registry=registry
    )

    register_agent(
        registry_service,
        name=diagnostic_name,
        queue_name=diagnostic_queue,
    )

    register_agent(
        registry_service,
        name=tutor_name,
        queue_name=tutor_queue,
    )

    register_agent(
        registry_service,
        name=exercise_name,
        queue_name=exercise_queue,
    )

    publisher_bus = RabbitMQEventBus()

    agent_buses = [
        RabbitMQEventBus(),
        RabbitMQEventBus(),
        RabbitMQEventBus(),
    ]

    result_bus = RabbitMQEventBus()

    received_results = []
    agent_threads = []
    result_thread = None

    try:
        agents = [
            (
                DiagnosticAgent,
                diagnostic_name,
                diagnostic_queue,
                agent_buses[0],
            ),
            (
                TutorAgent,
                tutor_name,
                tutor_queue,
                agent_buses[1],
            ),
            (
                ExerciseAgent,
                exercise_name,
                exercise_queue,
                agent_buses[2],
            ),
        ]

        for (
            agent_class,
            agent_name,
            queue_name,
            bus,
        ) in agents:
            agent = agent_class(
                agent_name=agent_name,
                queue_name=queue_name,
                event_bus=bus,
            )

            runtime = AgentRuntime(
                agent=agent,
                event_bus=bus,
                registry_service=registry_service,
                result_publisher=AgentResultPublisher(
                    event_bus=bus,
                    source=agent_name,
                ),
            )

            def make_callback(
                runtime_instance,
                consumer_bus,
            ):
                def callback(message):
                    runtime_instance.execute(message)
                    consumer_bus.channel.stop_consuming()

                return callback

            thread = threading.Thread(
                target=bus.consume_agent_messages,
                kwargs={
                    "queue_name": queue_name,
                    "callback": make_callback(
                        runtime,
                        bus,
                    ),
                },
                daemon=True,
            )

            agent_threads.append(thread)
            thread.start()

        router = WorkflowAgentRouter(
            registry_service=registry_service
        )

        result_handler = (
            TransactionalWorkflowResultHandler(
                uow_factory=uow_factory,
                router=router,
                dispatcher=AsyncWorkflowDispatcher(
                    event_bus=result_bus
                ),
                reply_queue=result_queue,
            )
        )

        def handle_result(
            message: AgentMessage,
        ) -> None:
            received_results.append(message)

            result_handler.handle(message)

            if len(received_results) >= 3:
                result_bus.channel.stop_consuming()

        result_thread = threading.Thread(
            target=result_bus.consume_agent_messages,
            kwargs={
                "queue_name": result_queue,
                "callback": handle_result,
            },
            daemon=True,
        )

        result_thread.start()

        # Give RabbitMQ consumers time to declare queues.
        time.sleep(0.5)

        definition = WorkflowDefinition(
            workflow_id=(
                "education-rabbit-postgres-e2e"
            ),
            name=(
                "Education RabbitMQ PostgreSQL E2E"
            ),
            steps=[
                WorkflowStep(
                    step_id="diagnostic",
                    name="Diagnostic",
                    agent_name=diagnostic_name,
                    position=0,
                ),
                WorkflowStep(
                    step_id="tutoring",
                    name="Tutoring",
                    agent_name=tutor_name,
                    position=1,
                ),
                WorkflowStep(
                    step_id="exercise",
                    name="Exercise",
                    agent_name=exercise_name,
                    position=2,
                ),
            ],
        )

        #
        # Initial workflow creation AND first dispatch
        # preparation happen in the SAME PostgreSQL UoW.
        #
        with uow_factory() as uow:
            engine = WorkflowEngine(
                repository=uow.workflows
            )

            execution = engine.create_execution(
                definition,
                execution_id=execution_id,
                input_data={
                    "student_id": "student-001",
                    "subject": "mathematics",
                    "question": (
                        "Combien font 27 + 18 ?"
                    ),
                },
            )

            engine.start(execution)

            coordinator = AsyncWorkflowCoordinator(
                engine=engine,
                router=router,
                dispatcher=AsyncWorkflowDispatcher(
                    event_bus=publisher_bus
                ),
                reply_queue=result_queue,
            )

            prepared = coordinator.prepare_next(
                execution,
                correlation_id=correlation_id,
            )

            assert prepared is not None
            assert prepared.step_id == "diagnostic"

            uow.outbox.add(
                OutboxMessage(
                    outbox_id=(
                        prepared.message.message_id
                    ),
                    queue_name=(
                        prepared.queue_name
                    ),
                    message=prepared.message,
                    created_at=datetime.now(
                        timezone.utc
                    ),
                )
            )

            uow.commit()

        #
        # From here on, every workflow transition is:
        #
        # PostgreSQL transaction
        # -> Outbox
        # -> RabbitMQ
        # -> Agent
        # -> RabbitMQ result
        # -> PostgreSQL transaction
        #
        outbox_publisher = OutboxPublisher(
            event_bus=publisher_bus,
            uow_factory=uow_factory,
        )

        deadline = time.time() + 15

        while time.time() < deadline:
            outbox_publisher.publish_pending()

            with uow_factory() as verification:
                restored = (
                    verification.workflows.get(
                        execution_id
                    )
                )

                if (
                    restored is not None
                    and restored.status
                    == WorkflowStatus.COMPLETED
                ):
                    break

            time.sleep(0.1)

        #
        # Final durable state.
        #
        with uow_factory() as verification:
            restored = verification.workflows.get(
                execution_id
            )

            assert restored is not None
            assert (
                restored.status
                == WorkflowStatus.COMPLETED
            )

            assert restored.current_step_id is None

            assert restored.context.outputs == {
                "diagnostic": {
                    "student_level": "beginner",
                    "difficulty": "addition",
                },
                "tutoring": {
                    "lesson": (
                        "addition-with-carry"
                    ),
                    "explanation": (
                        "27 + 18 = 45"
                    ),
                },
                "exercise": {
                    "exercise": "34 + 29",
                    "expected_answer": 63,
                },
            }

            assert (
                verification.outbox.pending()
                == []
            )

            for result in received_results:
                assert verification.inbox.contains(
                    result.message_id
                )

        assert len(received_results) == 3

        assert {
            result.metadata[
                "workflow_step_id"
            ]
            for result in received_results
        } == {
            "diagnostic",
            "tutoring",
            "exercise",
        }

        assert {
            result.correlation_id
            for result in received_results
        } == {
            correlation_id
        }

        for thread in agent_threads:
            thread.join(timeout=2)

        if result_thread is not None:
            result_thread.join(timeout=2)

        assert all(
            not thread.is_alive()
            for thread in agent_threads
        )

        assert (
            result_thread is not None
            and not result_thread.is_alive()
        )

    finally:
        for bus in agent_buses:
            if bus.connection.is_open:
                bus.close()

        if result_bus.connection.is_open:
            result_bus.close()

        if publisher_bus.connection.is_open:
            publisher_bus.close()

        clean_database()
