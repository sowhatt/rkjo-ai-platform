"""Embedding-space identity used to isolate vector searches."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EmbeddingSpace:
    provider: str
    model: str
    dimensions: int

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError(
                "Embedding provider must not be empty."
            )

        if not self.model.strip():
            raise ValueError(
                "Embedding model must not be empty."
            )

        if self.dimensions <= 0:
            raise ValueError(
                "Embedding dimensions must be greater than 0."
            )
