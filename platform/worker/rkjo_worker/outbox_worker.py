"""Production worker publishing durable workflow outbox messages."""

from __future__ import annotations

import os
import signal
import time
from collections.abc import Callable

from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.logging.logger import get_logger
from rkjo_worker.health import WorkerHealth
from rkjo_kernel.workflow.outbox_publisher import OutboxPublisher
from rkjo_kernel.workflow.postgres_unit_of_work import (
    PostgreSQLWorkflowUnitOfWork,
)


logger = get_logger(__name__)


class OutboxWorker:
    """Continuously publish committed workflow outbox messages."""

    def __init__(
        self,
        *,
        publisher: OutboxPublisher,
        poll_interval_seconds: float = 1.0,
        batch_size: int = 100,
        retry_initial_seconds: float = 1.0,
        retry_max_seconds: float = 30.0,
        retry_multiplier: float = 2.0,
        sleep_fn=time.sleep,
        publisher_factory: Callable[
            [], OutboxPublisher
        ] | None = None,
        health: WorkerHealth | None = None,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError(
                "poll_interval_seconds must be greater than zero."
            )

        if batch_size <= 0:
            raise ValueError(
                "batch_size must be greater than zero."
            )

        if retry_initial_seconds <= 0:
            raise ValueError(
                "retry_initial_seconds must be greater than zero."
            )

        if retry_max_seconds < retry_initial_seconds:
            raise ValueError(
                "retry_max_seconds must be greater than or equal "
                "to retry_initial_seconds."
            )

        if retry_multiplier < 1:
            raise ValueError(
                "retry_multiplier must be greater than or equal to one."
            )

        self.publisher = publisher
        self.poll_interval_seconds = poll_interval_seconds
        self.batch_size = batch_size
        self.retry_initial_seconds = retry_initial_seconds
        self.retry_max_seconds = retry_max_seconds
        self.retry_multiplier = retry_multiplier
        self.sleep_fn = sleep_fn
        self.publisher_factory = publisher_factory
        self.health = health or WorkerHealth(
            service_name="outbox-worker"
        )
        self._running = True

    def stop(self) -> None:
        self._running = False
        self.health.mark_stopped()

    def run(self) -> None:
        retry_delay = self.retry_initial_seconds

        while self._running:
            try:
                published = self.publisher.publish_pending(
                    limit=self.batch_size,
                )

                self.health.mark_ready()
                retry_delay = self.retry_initial_seconds

                if published == 0:
                    self.sleep_fn(
                        self.poll_interval_seconds
                    )

            except Exception as publish_exc:
                self.health.mark_not_ready(publish_exc)

                if not self._running:
                    break

                logger.exception(
                    "Outbox publication failed; retrying in %.3f seconds: %s",
                    retry_delay,
                    publish_exc,
                )

                if self.publisher_factory is not None:
                    try:
                        self.publisher = (
                            self.publisher_factory()
                        )
                    except Exception as rebuild_exc:
                        logger.exception(
                            "Failed to rebuild outbox publisher: %s",
                            rebuild_exc,
                        )

                self.sleep_fn(
                    retry_delay
                )

                retry_delay = min(
                    retry_delay * self.retry_multiplier,
                    self.retry_max_seconds,
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

    retry_initial_seconds = float(
        get_env(
            "RKJO_SERVICE_RETRY_INITIAL_SECONDS",
            "1.0",
        )
    )

    retry_max_seconds = float(
        get_env(
            "RKJO_SERVICE_RETRY_MAX_SECONDS",
            "30.0",
        )
    )

    retry_multiplier = float(
        get_env(
            "RKJO_SERVICE_RETRY_MULTIPLIER",
            "2.0",
        )
    )

    uow_factory = lambda: PostgreSQLWorkflowUnitOfWork(
        database_url
    )

    event_bus_holder: dict[
        str,
        RabbitMQEventBus,
    ] = {}

    def build_publisher() -> OutboxPublisher:
        previous_event_bus = event_bus_holder.get(
            "event_bus"
        )

        if previous_event_bus is not None:
            try:
                previous_event_bus.close()
            except Exception as close_exc:
                logger.warning(
                    "Failed to close previous RabbitMQ event bus: %s",
                    close_exc,
                    exc_info=True,
                )

        event_bus = RabbitMQEventBus()

        event_bus_holder[
            "event_bus"
        ] = event_bus

        return OutboxPublisher(
            event_bus=event_bus,
            uow_factory=uow_factory,
        )

    publisher = build_publisher()

    worker = OutboxWorker(
        publisher=publisher,
        publisher_factory=build_publisher,
        poll_interval_seconds=poll_interval_seconds,
        batch_size=batch_size,
        retry_initial_seconds=retry_initial_seconds,
        retry_max_seconds=retry_max_seconds,
        retry_multiplier=retry_multiplier,
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
        event_bus = event_bus_holder.get(
            "event_bus"
        )

        if event_bus is not None:
            event_bus.close()


if __name__ == "__main__":
    main()
