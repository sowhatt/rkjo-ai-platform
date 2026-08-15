"""RAG ingestion and semantic retrieval service."""

from __future__ import annotations

from rkjo_kernel.rag.chunking import TextChunker
from rkjo_kernel.rag.embedding import EmbeddingProvider
from rkjo_kernel.rag.models import (
    Document,
    RetrievedChunk,
)
from rkjo_kernel.rag.vector_store import VectorStore


class Retriever:
    """Coordinate chunking, embedding and vector search."""

    def __init__(
        self,
        *,
        chunker: TextChunker,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
    ) -> None:
        self.chunker = chunker
        self.embedding_provider = (
            embedding_provider
        )
        self.vector_store = vector_store

    def ingest(
        self,
        document: Document,
    ) -> int:
        chunks = self.chunker.split(
            document
        )

        for chunk in chunks:
            embedding = (
                self.embedding_provider
                .embed(
                    chunk.content
                )
            )

            self.vector_store.add(
                chunk=chunk,
                embedding=embedding,
            )

        return len(chunks)

    def retrieve(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[RetrievedChunk]:
        if not query.strip():
            raise ValueError(
                "Retrieval query must not be empty."
            )

        query_embedding = (
            self.embedding_provider
            .embed(
                query
            )
        )

        return self.vector_store.search(
            query_embedding=query_embedding,
            limit=limit,
        )
