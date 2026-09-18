"""RAG retrieval filters."""

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
    """Exact-match metadata and document allowlist filters."""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )
    document_ids: tuple[str, ...] | None = None

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

        normalized_document_ids: tuple[str, ...] | None = None
        if self.document_ids is not None:
            seen: set[str] = set()
            values: list[str] = []
            for raw_document_id in self.document_ids:
                document_id = str(raw_document_id).strip()
                if not document_id:
                    raise ValueError(
                        "Document filter ids must not be empty."
                    )
                if document_id in seen:
                    continue
                seen.add(document_id)
                values.append(document_id)
            normalized_document_ids = tuple(values)

        object.__setattr__(
            self,
            "metadata",
            normalized,
        )
        object.__setattr__(
            self,
            "document_ids",
            normalized_document_ids,
        )

    @property
    def is_empty(self) -> bool:
        return (
            not self.metadata
            and self.document_ids is None
        )

    def matches(
        self,
        metadata: dict[str, Any],
        *,
        document_id: str | None = None,
    ) -> bool:
        if not all(
            metadata.get(key) == value
            for key, value in self.metadata.items()
        ):
            return False

        if self.document_ids is None:
            return True

        return (
            document_id is not None
            and document_id in self.document_ids
        )


EMPTY_RETRIEVAL_FILTERS = RetrievalFilters()
