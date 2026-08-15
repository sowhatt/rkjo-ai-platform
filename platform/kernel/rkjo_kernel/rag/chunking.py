"""Simple deterministic text chunking."""

from __future__ import annotations

from rkjo_kernel.rag.models import (
    Document,
    DocumentChunk,
)


class TextChunker:
    """Split text into overlapping character windows."""

    def __init__(
        self,
        *,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError(
                "chunk_size must be greater than 0."
            )

        if overlap < 0:
            raise ValueError(
                "overlap must not be negative."
            )

        if overlap >= chunk_size:
            raise ValueError(
                "overlap must be smaller than chunk_size."
            )

        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(
        self,
        document: Document,
    ) -> list[DocumentChunk]:
        text = document.content.strip()

        chunks: list[DocumentChunk] = []

        start = 0
        index = 0

        while start < len(text):
            end = min(
                start + self.chunk_size,
                len(text),
            )

            content = text[
                start:end
            ].strip()

            if content:
                chunks.append(
                    DocumentChunk(
                        document_id=document.document_id,
                        content=content,
                        chunk_index=index,
                        metadata=dict(
                            document.metadata
                        ),
                    )
                )

                index += 1

            if end >= len(text):
                break

            start = (
                end - self.overlap
            )

        return chunks
