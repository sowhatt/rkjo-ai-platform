from __future__ import annotations

from abc import ABC, abstractmethod


class DocumentHashRegistry(ABC):

    @abstractmethod
    def contains(
        self,
        content_hash: str,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def register(
        self,
        *,
        content_hash: str,
        document_id: str,
    ) -> None:
        raise NotImplementedError


class InMemoryDocumentHashRegistry(
    DocumentHashRegistry
):

    def __init__(self) -> None:
        self._hashes: dict[str, str] = {}

    def contains(
        self,
        content_hash: str,
    ) -> bool:
        return content_hash in self._hashes

    def register(
        self,
        *,
        content_hash: str,
        document_id: str,
    ) -> None:
        self._hashes[content_hash] = document_id
