"""Publish asynchronous agent execution results."""

from __future__ import annotations

from typing import Any

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.messages.agent_message import AgentMessage


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


def _result_metadata(request: AgentMessage) -> dict[str, Any]:
    """Build result metadata while preserving transverse trace identity."""
    metadata: dict[str, Any] = {
        "request_message_id": request.message_id,
    }

    for key in _TRACE_METADATA_KEYS:
        value = request.metadata.get(key)
        if value is not None:
            metadata[key] = value

    return metadata


class AgentResultPublisher:
    """Publish workflow step results through EventBus."""

    def __init__(
        self,
        *,
        event_bus: EventBus,
        source: str,
    ) -> None:
        self.event_bus = event_bus
        self.source = source

    def publish_success(
        self,
        *,
        request: AgentMessage,
        result: Any,
    ) -> AgentMessage | None:
        """Publish a successful workflow step result."""

        reply_queue = request.metadata.get(
            "reply_queue"
        )

        if not reply_queue:
            return None

        response = AgentMessage(
            source=self.source,
            target="rkjo.workflow",
            message_type="workflow.step.result",
            correlation_id=request.correlation_id,
            payload={
                "success": True,
                "result": result,
            },
            metadata=_result_metadata(request),
        )

        self.event_bus.publish_agent_message(
            queue_name=reply_queue,
            message=response,
        )

        return response

    def publish_failure(
        self,
        *,
        request: AgentMessage,
        error: Exception,
    ) -> AgentMessage | None:
        """Publish a failed workflow step result."""

        reply_queue = request.metadata.get(
            "reply_queue"
        )

        if not reply_queue:
            return None

        response = AgentMessage(
            source=self.source,
            target="rkjo.workflow",
            message_type="workflow.step.result",
            correlation_id=request.correlation_id,
            payload={
                "success": False,
                "error": str(error),
            },
            metadata=_result_metadata(request),
        )

        self.event_bus.publish_agent_message(
            queue_name=reply_queue,
            message=response,
        )

        return response
