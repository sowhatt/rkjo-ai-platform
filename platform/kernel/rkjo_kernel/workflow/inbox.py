"""Inbox contracts for reliable workflow message processing."""

from __future__ import annotations

from typing import Protocol


class InboxStore(Protocol):
    """Persistence contract for consumed workflow messages."""

    def contains(
        self,
        message_id: str,
    ) -> bool:
        """Return whether a message was already processed."""
        ...

    def mark_processed(
        self,
        message_id: str,
    ) -> None:
        """Record a message as successfully processed."""
        ...
