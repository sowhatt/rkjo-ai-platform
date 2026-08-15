"""Embedding contracts for the RKJO knowledge layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
import math


class EmbeddingProvider(ABC):
    """Abstract semantic embedding provider."""

    @abstractmethod
    def embed(
        self,
        text: str,
    ) -> list[float]:
        raise NotImplementedError


class DeterministicEmbeddingProvider(
    EmbeddingProvider
):
    """Small deterministic embedding for tests/local development.

    This is not intended as a production semantic model.
    """

    def __init__(
        self,
        *,
        dimensions: int = 16,
    ) -> None:
        if dimensions <= 0:
            raise ValueError(
                "dimensions must be greater than 0."
            )

        self.dimensions = dimensions

    def embed(
        self,
        text: str,
    ) -> list[float]:
        if not text.strip():
            raise ValueError(
                "Text to embed must not be empty."
            )

        vector = [
            0.0
            for _ in range(
                self.dimensions
            )
        ]

        for index, character in enumerate(
            text.lower()
        ):
            bucket = (
                index
                % self.dimensions
            )

            vector[bucket] += (
                ord(character)
                / 255.0
            )

        norm = math.sqrt(
            sum(
                value * value
                for value in vector
            )
        )

        if norm == 0:
            return vector

        return [
            value / norm
            for value in vector
        ]
