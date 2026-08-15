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


class CitationContextBuilder:
    def __init__(
        self,
        *,
        max_characters: int = 12000,
    ) -> None:
        if max_characters <= 0:
            raise ValueError(
                "max_characters must be greater than 0."
            )

        self.max_characters = max_characters

    def build(
        self,
        results: list[SemanticSearchResult],
    ) -> BuiltContext:
        selected: list[SemanticSearchResult] = []
        blocks: list[str] = []
        current_size = 0

        for result in results:
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
                break

            blocks.append(block)
            selected.append(result)
            current_size += extra_size

        return BuiltContext(
            content="\n\n".join(blocks),
            results=selected,
        )
