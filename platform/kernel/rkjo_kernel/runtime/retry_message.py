"""Retry message construction."""

from __future__ import annotations

from copy import deepcopy

from rkjo_kernel.messages.agent_message import AgentMessage


def build_retry_message(
    *,
    original_message: AgentMessage,
) -> AgentMessage:
    """Create a new physical message for the same logical task."""

    metadata = deepcopy(
        original_message.metadata
    )

    current_attempt = int(
        metadata.get(
            "attempt",
            1,
        )
    )

    metadata["attempt"] = current_attempt + 1
    metadata["retry_of_message_id"] = (
        original_message.message_id
    )

    return AgentMessage(
        correlation_id=original_message.correlation_id,
        source=original_message.source,
        target=original_message.target,
        message_type=original_message.message_type,
        priority=original_message.priority,
        payload=deepcopy(
            original_message.payload
        ),
        metadata=metadata,
    )
