import pytest

from rkjo_kernel.rag.embedding_factory import (
    get_embedding_space,
)
from rkjo_kernel.rag.embedding_space import (
    EmbeddingSpace,
)


def test_embedding_space_validates_dimensions():
    with pytest.raises(ValueError):
        EmbeddingSpace(
            provider="openai",
            model="model-a",
            dimensions=0,
        )


def test_openai_embedding_space(monkeypatch):
    monkeypatch.setenv(
        "RKJO_EMBEDDING_PROVIDER",
        "openai",
    )
    monkeypatch.setenv(
        "RKJO_EMBEDDING_MODEL",
        "text-embedding-3-small",
    )
    monkeypatch.setenv(
        "RKJO_EMBEDDING_DIMENSIONS",
        "16",
    )

    space = get_embedding_space()

    assert space.provider == "openai"
    assert space.model == "text-embedding-3-small"
    assert space.dimensions == 16


def test_deterministic_embedding_space(monkeypatch):
    monkeypatch.setenv(
        "RKJO_EMBEDDING_PROVIDER",
        "deterministic",
    )
    monkeypatch.delenv(
        "RKJO_EMBEDDING_MODEL",
        raising=False,
    )
    monkeypatch.setenv(
        "RKJO_EMBEDDING_DIMENSIONS",
        "16",
    )

    space = get_embedding_space()

    assert space.provider == "deterministic"
    assert space.model == "deterministic-v1"
    assert space.dimensions == 16
