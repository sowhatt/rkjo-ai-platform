"""Production consumer for asynchronous workflow results."""

from __future__ import annotations

import os
import signal
import time
from collections.abc import Callable

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.logging.logger import get_logger
from rkjo_kernel.registry.descriptor import AgentStatus
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.workflow.agent_routing import WorkflowAgentRouter
from rkjo_kernel.workflow.async_dispatch import AsyncWorkflowDispatcher
from rkjo_kernel.workflow.postgres_unit_of_work import (
    PostgreSQLWorkflowUnitOfWork,
)
from rkjo_kernel.workflow.transactional_result_handler import (
    TransactionalWorkflowResultHandler,
)
from rkjo_worker.agent_catalog import (
    register_platform_worker,
)


logger = get_logger(__name__)


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


def build_result_handler(
    *,
    event_bus: EventBus,
) -> tuple[
    str,
    TransactionalWorkflowResultHandler,
]:
    """Build the production workflow result handler."""

    database_url = get_env(
        "RKJO_DATABASE_URL",
        "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
    )

    result_queue = get_env(
        "RKJO_WORKFLOW_RESULT_QUEUE",
        "rkjo.workflow.results",
    )

    registry = AgentRegistry()

    registry_service = RegistryService(
        registry=registry,
    )

    register_platform_worker(
        registry_service,
        status=AgentStatus.AVAILABLE,
    )

    router = WorkflowAgentRouter(
        registry_service=registry_service,
    )

    dispatcher = AsyncWorkflowDispatcher(
        event_bus=event_bus,
    )

    uow_factory = lambda: PostgreSQLWorkflowUnitOfWork(
        database_url
    )

    handler = TransactionalWorkflowResultHandler(
        uow_factory=uow_factory,
        router=router,
        dispatcher=dispatcher,
        reply_queue=result_queue,
    )

    return result_queue, handler


class WorkflowResultConsumer:
    """Supervise the production workflow result consumer."""

    def __init__(
        self,
        *,
        event_bus_factory: Callable[[], EventBus],
        handler_builder=build_result_handler,
        retry_initial_seconds: float = 1.0,
        retry_max_seconds: float = 30.0,
        retry_multiplier: float = 2.0,
        sleep_fn=time.sleep,
    ) -> None:
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

        self.event_bus_factory = event_bus_factory
        self.handler_builder = handler_builder
        self.retry_initial_seconds = retry_initial_seconds
        self.retry_max_seconds = retry_max_seconds
        self.retry_multiplier = retry_multiplier
        self.sleep_fn = sleep_fn
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        retry_delay = self.retry_initial_seconds

        while self._running:
            event_bus: EventBus | None = None

            try:
                event_bus = self.event_bus_factory()

                result_queue, handler = self.handler_builder(
                    event_bus=event_bus,
                )

                logger.info(
                    "Consuming workflow results from queue '%s'.",
                    result_queue,
                )

                event_bus.consume_agent_messages(
                    queue_name=result_queue,
                    callback=handler.handle,
                )

                return

            except KeyboardInterrupt:
                logger.info(
                    "Workflow result consumer interrupted."
                )
                return

            except Exception as exc:
                if not self._running:
                    return

                logger.exception(
                    "Workflow result consumer failed; "
                    "retrying in %.3f seconds: %s",
                    retry_delay,
                    exc,
                )

                self.sleep_fn(
                    retry_delay
                )

                retry_delay = min(
                    retry_delay * self.retry_multiplier,
                    self.retry_max_seconds,
                )

            finally:
                if event_bus is not None:
                    try:
                        event_bus.close()
                    except Exception as close_exc:
                        logger.warning(
                            "Failed to close workflow result "
                            "RabbitMQ event bus: %s",
                            close_exc,
                            exc_info=True,
                        )


def main() -> None:
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

    consumer = WorkflowResultConsumer(
        event_bus_factory=RabbitMQEventBus,
        retry_initial_seconds=retry_initial_seconds,
        retry_max_seconds=retry_max_seconds,
        retry_multiplier=retry_multiplier,
    )

    def _stop_handler(
        signum,
        frame,
    ) -> None:
        raise KeyboardInterrupt

    signal.signal(
        signal.SIGTERM,
        _stop_handler,
    )
    signal.signal(
        signal.SIGINT,
        _stop_handler,
    )

    consumer.run()


if __name__ == "__main__":
    main()
