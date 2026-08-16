"""Reranker configuration factory."""

from __future__ import annotations

import os


from rkjo_kernel.rag.relevance_filter import (
    RelevanceFilter,
    RelevanceFilterConfig,
)

from rkjo_kernel.rag.reranker import (
    LexicalOverlapReranker,
    NoOpReranker,
    Reranker,
)


def build_reranker() -> Reranker:
    provider = os.getenv(
        "RKJO_RERANKER",
        "none",
    ).strip().lower()

    if provider in {
        "",
        "none",
        "noop",
    }:
        return NoOpReranker()

    if provider == "lexical":
        return LexicalOverlapReranker()

    raise RuntimeError(
        "Unsupported RKJO_RERANKER: "
        f"{provider}"
    )


def get_reranking_candidate_multiplier() -> int:
    raw = os.getenv(
        "RKJO_RERANKING_CANDIDATE_MULTIPLIER",
        "4",
    )

    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(
            "RKJO_RERANKING_CANDIDATE_MULTIPLIER "
            "must be an integer."
        ) from exc

    if not 1 <= value <= 20:
        raise RuntimeError(
            "RKJO_RERANKING_CANDIDATE_MULTIPLIER "
            "must be between 1 and 20."
        )

    return value



def build_relevance_filter() -> RelevanceFilter:
    return RelevanceFilter(
        RelevanceFilterConfig(
            minimum_score=_read_float(
                "RKJO_RERANKING_MIN_SCORE",
                0.20,
            ),
            relative_to_top=_read_float(
                "RKJO_RERANKING_RELATIVE_TO_TOP",
                0.50,
            ),
            minimum_results=_read_int(
                "RKJO_RERANKING_MIN_RESULTS",
                1,
            ),
        )
    )


def _read_float(
    name: str,
    default: float,
) -> float:
    raw = os.getenv(name)

    if raw is None:
        return default

    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"{name} must be a number."
        ) from exc


def _read_int(
    name: str,
    default: int,
) -> int:
    raw = os.getenv(name)

    if raw is None:
        return default

    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"{name} must be an integer."
        ) from exc
