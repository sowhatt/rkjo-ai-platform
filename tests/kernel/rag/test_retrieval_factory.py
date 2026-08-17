import pytest

from rkjo_kernel.rag.retrieval_factory import (
    get_retrieval_mode,
    get_rrf_k,
)


def test_retrieval_mode_defaults_to_vector(
    monkeypatch,
):
    monkeypatch.delenv(
        "RKJO_RETRIEVAL_MODE",
        raising=False,
    )

    assert (
        get_retrieval_mode()
        == "vector"
    )


def test_hybrid_mode(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_RETRIEVAL_MODE",
        "hybrid",
    )

    assert (
        get_retrieval_mode()
        == "hybrid"
    )


def test_unknown_mode_is_rejected(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_RETRIEVAL_MODE",
        "magic",
    )

    with pytest.raises(
        RuntimeError,
        match="vector.*hybrid",
    ):
        get_retrieval_mode()


def test_rrf_k_defaults_to_60(
    monkeypatch,
):
    monkeypatch.delenv(
        "RKJO_HYBRID_RRF_K",
        raising=False,
    )

    assert get_rrf_k() == 60


def test_invalid_rrf_k_is_rejected(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_HYBRID_RRF_K",
        "0",
    )

    with pytest.raises(
        RuntimeError,
        match="greater than 0",
    ):
        get_rrf_k()
