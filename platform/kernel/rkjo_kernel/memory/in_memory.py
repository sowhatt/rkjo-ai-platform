from __future__ import annotations

from threading import RLock

from .models import MemoryItem, MemoryQuery


class InMemoryMemoryStore:
    """Thread-safe in-memory implementation of the MemoryPort contract.

    Intended for tests, local development and ephemeral execution memory.
    Tenant isolation is enforced by every read and delete operation.
    """

    def __init__(self) -> None:
        self._items: dict[str, MemoryItem] = {}
        self._lock = RLock()

    def write(self, item: MemoryItem) -> MemoryItem:
        with self._lock:
            existing = self._items.get(item.memory_id)

            if (
                existing is not None
                and existing.tenant_id != item.tenant_id
            ):
                raise ValueError(
                    "Cannot overwrite memory across tenant boundary"
                )

            self._items[item.memory_id] = item

        return item

    def get(
        self,
        memory_id: str,
        *,
        tenant_id: str,
    ) -> MemoryItem | None:
        if not tenant_id.strip():
            raise ValueError("tenant_id must not be empty")

        with self._lock:
            item = self._items.get(memory_id)

        if item is None or item.tenant_id != tenant_id:
            return None

        return item

    def search(self, query: MemoryQuery) -> list[MemoryItem]:
        with self._lock:
            candidates = tuple(self._items.values())

        matches = [
            item
            for item in candidates
            if self._matches(item, query)
        ]

        matches.sort(
            key=lambda item: (
                item.importance,
                item.created_at,
                item.memory_id,
            ),
            reverse=True,
        )

        return matches[: query.limit]

    def delete(
        self,
        memory_id: str,
        *,
        tenant_id: str,
    ) -> bool:
        if not tenant_id.strip():
            raise ValueError("tenant_id must not be empty")

        with self._lock:
            item = self._items.get(memory_id)

            if item is None or item.tenant_id != tenant_id:
                return False

            del self._items[memory_id]
            return True

    @staticmethod
    def _matches(
        item: MemoryItem,
        query: MemoryQuery,
    ) -> bool:
        if item.tenant_id != query.tenant_id:
            return False

        if query.scopes and item.scope not in query.scopes:
            return False

        if (
            query.memory_types
            and item.memory_type not in query.memory_types
        ):
            return False

        if (
            query.mission_id is not None
            and item.mission_id != query.mission_id
        ):
            return False

        if (
            query.execution_id is not None
            and item.execution_id != query.execution_id
        ):
            return False

        if (
            query.user_id is not None
            and item.user_id != query.user_id
        ):
            return False

        if (
            query.domain is not None
            and item.domain != query.domain
        ):
            return False

        if (
            query.entity_id is not None
            and item.entity_id != query.entity_id
        ):
            return False

        if (
            query.min_importance is not None
            and item.importance < query.min_importance
        ):
            return False

        if query.text:
            needle = query.text.casefold().strip()

            if needle and needle not in item.content.casefold():
                return False

        if query.metadata:
            for key, expected_value in query.metadata.items():
                if item.metadata.get(key) != expected_value:
                    return False

        return True
