"""Idempotency support for workflow result processing."""

from __future__ import annotations

from typing import Protocol


class ProcessedMessageStore(Protocol):
    """Track message identifiers already applied."""

    def contains(
        self,
        message_id: str,
    ) -> bool:
        ...

    def mark_processed(
        self,
        message_id: str,
    ) -> None:
        ...


class InMemoryProcessedMessageStore:
    """In-memory processed-message registry."""

    def __init__(self) -> None:
        self._message_ids: set[str] = set()

    def contains(
        self,
        message_id: str,
    ) -> bool:
        return message_id in self._message_ids

    def mark_processed(
        self,
        message_id: str,
    ) -> None:
        self._message_ids.add(message_id)
