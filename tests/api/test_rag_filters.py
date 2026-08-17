import pytest
from pydantic import ValidationError

from rkjo_api.rag_filters import (
    RAGMetadataFilters,
)


def test_allowed_filters_convert_to_retrieval_filters():
    filters = RAGMetadataFilters(
        country="benin",
        domain="agriculture",
        tenant_id="tenant-a",
        year=2026,
    )

    retrieval = (
        filters.to_retrieval_filters()
    )

    assert retrieval.metadata == {
        "country": "benin",
        "domain": "agriculture",
        "tenant_id": "tenant-a",
        "year": 2026,
    }


def test_filter_strings_are_trimmed():
    filters = RAGMetadataFilters(
        country="  benin  ",
    )

    assert filters.country == "benin"


def test_unknown_filter_is_rejected():
    with pytest.raises(
        ValidationError,
    ):
        RAGMetadataFilters(
            secret_field="forbidden",
        )


def test_empty_filter_value_is_rejected():
    with pytest.raises(
        ValidationError,
        match="must not be empty",
    ):
        RAGMetadataFilters(
            domain="   ",
        )


def test_invalid_year_is_rejected():
    with pytest.raises(
        ValidationError,
    ):
        RAGMetadataFilters(
            year=1500,
        )
