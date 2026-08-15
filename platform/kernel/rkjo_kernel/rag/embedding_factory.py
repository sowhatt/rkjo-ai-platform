"""Embedding provider configuration and factory."""

from __future__ import annotations

import os

from rkjo_kernel.rag.embedding import (
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
)
from rkjo_kernel.rag.openai_embedding import (
    OpenAIEmbeddingProvider,
)


def get_embedding_dimensions() -> int:
    raw = os.getenv(
        "RKJO_EMBEDDING_DIMENSIONS",
        "16",
    )

    try:
        dimensions = int(raw)
    except ValueError as exc:
        raise RuntimeError(
            "RKJO_EMBEDDING_DIMENSIONS "
            "must be an integer."
        ) from exc

    if dimensions <= 0:
        raise RuntimeError(
            "RKJO_EMBEDDING_DIMENSIONS "
            "must be greater than 0."
        )

    return dimensions


def build_embedding_provider() -> EmbeddingProvider:
    provider = os.getenv(
        "RKJO_EMBEDDING_PROVIDER",
        "deterministic",
    ).strip().lower()

    dimensions = (
        get_embedding_dimensions()
    )

    if provider == "deterministic":
        return (
            DeterministicEmbeddingProvider(
                dimensions=dimensions
            )
        )

    if provider == "openai":
        api_key = os.getenv(
            "OPENAI_API_KEY",
            "",
        ).strip()

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required "
                "when RKJO_EMBEDDING_PROVIDER=openai."
            )

        model = os.getenv(
            "RKJO_EMBEDDING_MODEL",
            "text-embedding-3-small",
        ).strip()

        timeout = float(
            os.getenv(
                "RKJO_EMBEDDING_TIMEOUT_SECONDS",
                "10",
            )
        )

        retries = int(
            os.getenv(
                "RKJO_EMBEDDING_MAX_RETRIES",
                "2",
            )
        )

        return OpenAIEmbeddingProvider(
            api_key=api_key,
            model=model,
            dimensions=dimensions,
            timeout_seconds=timeout,
            max_retries=retries,
        )

    raise RuntimeError(
        "Unsupported RKJO_EMBEDDING_PROVIDER: "
        f"{provider}"
    )
