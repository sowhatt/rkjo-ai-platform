"""Validated public metadata filters for RAG APIs."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from rkjo_kernel.rag.retrieval_filters import (
    RetrievalFilters,
)


class RAGMetadataFilters(BaseModel):
    """Public allow-listed metadata filters."""

    model_config = ConfigDict(
        extra="forbid",
    )

    country: str | None = Field(
        default=None,
        max_length=100,
    )
    domain: str | None = Field(
        default=None,
        max_length=100,
    )
    tenant_id: str | None = Field(
        default=None,
        max_length=200,
    )
    document_type: str | None = Field(
        default=None,
        max_length=100,
    )
    source: str | None = Field(
        default=None,
        max_length=200,
    )
    organization: str | None = Field(
        default=None,
        max_length=200,
    )
    year: int | None = Field(
        default=None,
        ge=1900,
        le=2200,
    )

    @field_validator(
        "country",
        "domain",
        "tenant_id",
        "document_type",
        "source",
        "organization",
    )
    @classmethod
    def validate_non_empty_string(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Filter values must not be empty."
            )

        return normalized

    def to_retrieval_filters(
        self,
    ) -> RetrievalFilters:
        metadata = self.model_dump(
            exclude_none=True,
        )

        return RetrievalFilters(
            metadata=metadata
        )
