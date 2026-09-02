"""Publication of durable workflow outbox messages."""

from __future__ import annotations

from collections.abc import Callable

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.workflow.unit_of_work import (
    WorkflowUnitOfWork,
)


WorkflowUnitOfWorkFactory = Callable[
    [],
    WorkflowUnitOfWork,
]


class OutboxPublisher:
    """Publish committed workflow outbox messages."""

    def __init__(
        self,
        *,
        event_bus: EventBus,
        uow_factory: WorkflowUnitOfWorkFactory,
    ) -> None:
        self.event_bus = event_bus
        self.uow_factory = uow_factory

    def publish_pending(
        self,
        *,
        limit: int = 100,
    ) -> int:
        """Publish up to ``limit`` pending outbox messages."""
        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        published_count = 0

        for _ in range(limit):
            published = self._publish_one()

            if not published:
                break

            published_count += 1

        return published_count

    def _publish_one(self) -> bool:
        """Publish and acknowledge one pending message."""
        with self.uow_factory() as uow:
            pending = uow.outbox.pending(
                limit=1,
            )

            if not pending:
                return False

            outbox_message = pending[0]

            self.event_bus.publish_agent_message(
                queue_name=outbox_message.queue_name,
                message=outbox_message.message,
            )

            uow.outbox.mark_published(
                outbox_message.outbox_id
            )

            uow.commit()

        return True
