import pytest

from rkjo_kernel.rag.reranker import (
    LexicalOverlapReranker,
    NoOpReranker,
)
from rkjo_kernel.rag.reranking_factory import (
    build_reranker,
    get_reranking_candidate_multiplier,
)


def test_factory_defaults_to_noop(
    monkeypatch,
):
    monkeypatch.delenv(
        "RKJO_RERANKER",
        raising=False,
    )

    assert isinstance(
        build_reranker(),
        NoOpReranker,
    )


def test_factory_builds_lexical(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_RERANKER",
        "lexical",
    )

    assert isinstance(
        build_reranker(),
        LexicalOverlapReranker,
    )


def test_unknown_reranker_is_rejected(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_RERANKER",
        "unknown",
    )

    with pytest.raises(
        RuntimeError,
        match="Unsupported",
    ):
        build_reranker()


def test_candidate_multiplier(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_RERANKING_CANDIDATE_MULTIPLIER",
        "4",
    )

    assert (
        get_reranking_candidate_multiplier()
        == 4
    )


def test_invalid_candidate_multiplier(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_RERANKING_CANDIDATE_MULTIPLIER",
        "0",
    )

    with pytest.raises(
        RuntimeError,
        match="between 1 and 20",
    ):
        get_reranking_candidate_multiplier()
