"""Dead-letter publishing for failed agent messages."""

from __future__ import annotations

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.logging.logger import get_logger
from rkjo_kernel.logging.structured import structured_log
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.monitoring.metrics import MetricsRegistry


_TRACE_METADATA_KEYS = (
    "trace_id",
    "mission_id",
    "workflow_execution_id",
    "workflow_step_id",
    "agent_id",
    "capability_name",
    "tool_call_id",
    "tenant_id",
    "user_id",
    "request_id",
    "parent_span_id",
)


class DeadLetterPublisher:
    """Publish permanently failed messages to a DLQ."""

    def __init__(
        self,
        *,
        event_bus: EventBus,
        queue_name: str,
        source: str = "rkjo.runtime",
        metrics: MetricsRegistry | None = None,
    ) -> None:
        if not queue_name or not queue_name.strip():
            raise ValueError(
                "queue_name must not be empty."
            )

        self.event_bus = event_bus
        self.queue_name = queue_name
        self.source = source
        self.metrics = metrics
        self.logger = get_logger(
            "rkjo.runtime.dlq"
        )

    def publish(
        self,
        *,
        original_message: AgentMessage,
        reason: str,
    ) -> AgentMessage:
        """Publish a dead-letter message."""

        metadata = {
            "original_message_id": original_message.message_id,
            "attempt": original_message.metadata.get(
                "attempt",
                1,
            ),
        }

        for key in _TRACE_METADATA_KEYS:
            value = original_message.metadata.get(key)
            if value is not None:
                metadata[key] = value

        dead_letter = AgentMessage(
            source=self.source,
            target="rkjo.dlq",
            message_type="workflow.step.dead_letter",
            correlation_id=original_message.correlation_id,
            payload={
                "original_message": (
                    original_message.model_dump(
                        mode="json"
                    )
                ),
                "reason": reason,
            },
            metadata=metadata,
        )

        self.event_bus.publish_agent_message(
            queue_name=self.queue_name,
            message=dead_letter,
        )

        if self.metrics is not None:
            self.metrics.increment(
                "runtime.dead_letter"
            )

        structured_log(
            self.logger,
            event="runtime.dead_letter",
            trace_id=original_message.metadata.get(
                "trace_id"
            ),
            mission_id=original_message.metadata.get(
                "mission_id"
            ),
            message_id=original_message.message_id,
            dead_letter_message_id=dead_letter.message_id,
            correlation_id=original_message.correlation_id,
            execution_id=original_message.metadata.get(
                "workflow_execution_id"
            ),
            step_id=original_message.metadata.get(
                "workflow_step_id"
            ),
            capability_name=original_message.metadata.get(
                "capability_name"
            ),
            queue_name=self.queue_name,
            attempt=original_message.metadata.get(
                "attempt",
                1,
            ),
            reason=reason,
        )

        return dead_letter
