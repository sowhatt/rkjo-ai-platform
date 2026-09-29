from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import MemoryItem, MemoryQuery


@runtime_checkable
class MemoryPort(Protocol):
    """Storage-neutral contract implemented by memory backends."""

    def write(self, item: MemoryItem) -> MemoryItem:
        ...

    def get(
        self,
        memory_id: str,
        *,
        tenant_id: str,
    ) -> MemoryItem | None:
        ...

    def search(self, query: MemoryQuery) -> list[MemoryItem]:
        ...

    def delete(
        self,
        memory_id: str,
        *,
        tenant_id: str,
    ) -> bool:
        ...
