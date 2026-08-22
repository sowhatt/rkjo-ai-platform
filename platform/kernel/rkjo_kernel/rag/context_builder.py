"""Build bounded, citation-aware context for RAG generation."""

from __future__ import annotations

from dataclasses import dataclass

from rkjo_kernel.rag.semantic_search import (
    SemanticSearchResult,
)


@dataclass(frozen=True, slots=True)
class BuiltContext:
    content: str
    results: list[SemanticSearchResult]
    character_count: int
    truncated: bool


class CitationContextBuilder:
    def __init__(
        self,
        *,
        max_characters: int = 12000,
        max_chunks: int = 5,
    ) -> None:
        if max_characters <= 0:
            raise ValueError(
                "max_characters must be greater than 0."
            )

        if max_chunks <= 0:
            raise ValueError(
                "max_chunks must be greater than 0."
            )

        self.max_characters = max_characters
        self.max_chunks = max_chunks

    def build(
        self,
        results: list[SemanticSearchResult],
    ) -> BuiltContext:
        selected: list[SemanticSearchResult] = []
        blocks: list[str] = []
        seen: set[tuple[str, str]] = set()

        current_size = 0
        truncated = False

        for result in results:
            deduplication_key = (
                result.document_id,
                result.content,
            )

            if deduplication_key in seen:
                continue

            if len(selected) >= self.max_chunks:
                truncated = True
                break

            citation = len(selected) + 1

            block = (
                f"[{citation}]\n"
                f"document_id: {result.document_id}\n"
                f"chunk_id: {result.chunk_id}\n"
                f"content:\n{result.content}"
            )

            extra_size = len(block)

            if blocks:
                extra_size += 2

            if (
                current_size + extra_size
                > self.max_characters
            ):
                truncated = True
                continue

            seen.add(deduplication_key)
            blocks.append(block)
            selected.append(result)
            current_size += extra_size

        content = "\n\n".join(blocks)

        return BuiltContext(
            content=content,
            results=selected,
            character_count=len(content),
            truncated=truncated,
        )
