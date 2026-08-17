"""Metadata-aware RAG retrieval filters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_ALLOWED_VALUE_TYPES = (
    str,
    int,
    float,
    bool,
)


@dataclass(frozen=True, slots=True)
class RetrievalFilters:
    """Exact-match metadata filters applied before ranking."""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        normalized: dict[str, Any] = {}

        for raw_key, value in self.metadata.items():
            key = str(raw_key).strip()

            if not key:
                raise ValueError(
                    "Metadata filter keys must not be empty."
                )

            if not isinstance(
                value,
                _ALLOWED_VALUE_TYPES,
            ):
                raise ValueError(
                    "Metadata filter values must be "
                    "scalar JSON values."
                )

            if (
                isinstance(value, str)
                and not value.strip()
            ):
                raise ValueError(
                    "String metadata filter values "
                    "must not be empty."
                )

            normalized[key] = value

        object.__setattr__(
            self,
            "metadata",
            normalized,
        )

    @property
    def is_empty(self) -> bool:
        return not self.metadata

    def matches(
        self,
        metadata: dict[str, Any],
    ) -> bool:
        return all(
            metadata.get(key) == value
            for key, value in self.metadata.items()
        )


EMPTY_RETRIEVAL_FILTERS = RetrievalFilters()
