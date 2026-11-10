"""Consume durable multimodal job events and enqueue channel notifications.

Uses the existing transactional Workflow inbox/outbox; RabbitMQ acknowledgements
occur only after the database transaction commits.
"""
from __future__ import annotations

import os
import signal

from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.multimodal.job_events import MultimodalJobEventHandler
from rkjo_kernel.multimodal.postgres_jobs import PostgreSQLIngestionJobAdapter
from rkjo_kernel.workflow.postgres_unit_of_work import PostgreSQLWorkflowUnitOfWork
from rkjo_worker.multimodal_notification_consumer import MultimodalNotificationConsumer

DEFAULT_JOB_QUEUE = "rkjo.multimodal.jobs"
DEFAULT_NOTIFICATION_QUEUE = "rkjo.multimodal.notifications"


def build_job_event_consumer(
    *, database_url: str, event_bus_factory=RabbitMQEventBus,
    job_queue: str = DEFAULT_JOB_QUEUE,
    notification_queue: str = DEFAULT_NOTIFICATION_QUEUE,
) -> MultimodalNotificationConsumer:
    """Assemble only established RKJO ports; schema bootstrap is separate."""
    if not database_url.strip():
        raise ValueError("Database URL required.")
    handler = MultimodalJobEventHandler(
        jobs=PostgreSQLIngestionJobAdapter(database_url, event_queue=job_queue),
        uow_factory=lambda: PostgreSQLWorkflowUnitOfWork(database_url),
        notification_queue=notification_queue,
    )
    # The generic supervised consumer accepts any AgentMessage handler.
    return MultimodalNotificationConsumer(
        event_bus_factory=event_bus_factory,
        handler=handler,
        queue_name=job_queue,
    )


def main() -> None:
    consumer = build_job_event_consumer(
        database_url=os.environ["RKJO_DATABASE_URL"],
        job_queue=os.getenv("RKJO_MULTIMODAL_JOB_QUEUE", DEFAULT_JOB_QUEUE),
        notification_queue=os.getenv(
            "RKJO_MULTIMODAL_NOTIFICATION_QUEUE", DEFAULT_NOTIFICATION_QUEUE
        ),
    )

    def stop(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    consumer.run()


if __name__ == "__main__":
    main()
