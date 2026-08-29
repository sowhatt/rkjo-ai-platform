"""Production worker publishing durable workflow outbox messages."""

from __future__ import annotations

import os
import signal
import time

from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.workflow.outbox_publisher import OutboxPublisher
from rkjo_kernel.workflow.postgres_unit_of_work import (
    PostgreSQLWorkflowUnitOfWork,
)


class OutboxWorker:
    """Continuously publish committed workflow outbox messages."""

    def __init__(
        self,
        *,
        publisher: OutboxPublisher,
        poll_interval_seconds: float = 1.0,
        batch_size: int = 100,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError(
                "poll_interval_seconds must be greater than zero."
            )

        if batch_size <= 0:
            raise ValueError(
                "batch_size must be greater than zero."
            )

        self.publisher = publisher
        self.poll_interval_seconds = poll_interval_seconds
        self.batch_size = batch_size
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        while self._running:
            published = self.publisher.publish_pending(
                limit=self.batch_size,
            )

            if published == 0:
                time.sleep(
                    self.poll_interval_seconds
                )


def get_env(
    name: str,
    default: str,
) -> str:
    value = os.getenv(
        name,
        default,
    ).strip()

    if not value:
        raise RuntimeError(
            f"{name} must not be empty."
        )

    return value


def main() -> None:
    database_url = get_env(
        "RKJO_DATABASE_URL",
        "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
    )

    poll_interval_seconds = float(
        get_env(
            "RKJO_OUTBOX_POLL_INTERVAL_SECONDS",
            "1.0",
        )
    )

    batch_size = int(
        get_env(
            "RKJO_OUTBOX_BATCH_SIZE",
            "100",
        )
    )

    event_bus = RabbitMQEventBus()

    uow_factory = lambda: PostgreSQLWorkflowUnitOfWork(
        database_url
    )

    publisher = OutboxPublisher(
        event_bus=event_bus,
        uow_factory=uow_factory,
    )

    worker = OutboxWorker(
        publisher=publisher,
        poll_interval_seconds=poll_interval_seconds,
        batch_size=batch_size,
    )

    def _stop_handler(
        signum,
        frame,
    ) -> None:
        worker.stop()

    signal.signal(
        signal.SIGTERM,
        _stop_handler,
    )

    signal.signal(
        signal.SIGINT,
        _stop_handler,
    )

    try:
        worker.run()
    finally:
        event_bus.close()


if __name__ == "__main__":
    main()
