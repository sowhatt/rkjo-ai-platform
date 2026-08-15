"""OpenAI production embedding provider."""

from __future__ import annotations

from collections.abc import Sequence

from openai import OpenAI

from rkjo_kernel.rag.embedding import EmbeddingProvider


class OpenAIEmbeddingProvider(
    EmbeddingProvider
):
    """Generate semantic embeddings with the OpenAI Embeddings API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimensions: int = 16,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        client: OpenAI | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError(
                "api_key must not be empty."
            )

        if not model.strip():
            raise ValueError(
                "model must not be empty."
            )

        if dimensions <= 0:
            raise ValueError(
                "dimensions must be greater than 0."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than 0."
            )

        if max_retries < 0:
            raise ValueError(
                "max_retries must not be negative."
            )

        self.model = model
        self.dimensions = dimensions

        self.client = (
            client
            or OpenAI(
                api_key=api_key,
                timeout=timeout_seconds,
                max_retries=max_retries,
            )
        )

    def embed(
        self,
        text: str,
    ) -> list[float]:
        if not text.strip():
            raise ValueError(
                "Text to embed must not be empty."
            )

        response = (
            self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions,
                encoding_format="float",
            )
        )

        if not response.data:
            raise RuntimeError(
                "Embedding provider returned no data."
            )

        embedding = list(
            response.data[0].embedding
        )

        self._validate_dimensions(
            embedding
        )

        return embedding

    def embed_batch(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        if not texts:
            raise ValueError(
                "Embedding batch must not be empty."
            )

        normalized = [
            text
            for text in texts
            if text.strip()
        ]

        if len(normalized) != len(texts):
            raise ValueError(
                "Embedding batch contains empty text."
            )

        response = (
            self.client.embeddings.create(
                model=self.model,
                input=list(normalized),
                dimensions=self.dimensions,
                encoding_format="float",
            )
        )

        ordered = sorted(
            response.data,
            key=lambda item: item.index,
        )

        embeddings = [
            list(item.embedding)
            for item in ordered
        ]

        if (
            len(embeddings)
            != len(normalized)
        ):
            raise RuntimeError(
                "Embedding provider returned an "
                "unexpected number of vectors."
            )

        for embedding in embeddings:
            self._validate_dimensions(
                embedding
            )

        return embeddings

    def _validate_dimensions(
        self,
        embedding: list[float],
    ) -> None:
        if len(embedding) != self.dimensions:
            raise RuntimeError(
                "Embedding dimension mismatch: "
                f"expected {self.dimensions}, "
                f"received {len(embedding)}."
            )
