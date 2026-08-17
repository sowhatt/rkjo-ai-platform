"""Configuration helpers for RKJO retrieval modes."""

from __future__ import annotations

import os


def get_retrieval_mode() -> str:
    mode = os.getenv(
        "RKJO_RETRIEVAL_MODE",
        "vector",
    ).strip().lower()

    if mode not in {
        "vector",
        "hybrid",
    }:
        raise RuntimeError(
            "RKJO_RETRIEVAL_MODE must be "
            "'vector' or 'hybrid'."
        )

    return mode


def get_rrf_k() -> int:
    raw = os.getenv(
        "RKJO_HYBRID_RRF_K",
        "60",
    )

    try:
        value = int(raw)

    except ValueError as exc:
        raise RuntimeError(
            "RKJO_HYBRID_RRF_K must be "
            "an integer."
        ) from exc

    if value <= 0:
        raise RuntimeError(
            "RKJO_HYBRID_RRF_K must be "
            "greater than 0."
        )

    return value
