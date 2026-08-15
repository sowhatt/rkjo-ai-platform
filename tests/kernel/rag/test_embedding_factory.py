import pytest

from rkjo_kernel.rag.embedding import (
    DeterministicEmbeddingProvider,
)
from rkjo_kernel.rag.embedding_factory import (
    build_embedding_provider,
)


def test_factory_defaults_to_deterministic(
    monkeypatch,
):
    monkeypatch.delenv(
        "RKJO_EMBEDDING_PROVIDER",
        raising=False,
    )

    provider = build_embedding_provider()

    assert isinstance(
        provider,
        DeterministicEmbeddingProvider,
    )


def test_openai_requires_api_key(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_EMBEDDING_PROVIDER",
        "openai",
    )

    monkeypatch.delenv(
        "OPENAI_API_KEY",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="OPENAI_API_KEY",
    ):
        build_embedding_provider()


def test_unknown_provider_is_rejected(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_EMBEDDING_PROVIDER",
        "unknown",
    )

    with pytest.raises(
        RuntimeError,
        match="Unsupported",
    ):
        build_embedding_provider()
