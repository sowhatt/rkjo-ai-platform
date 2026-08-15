"""Structured logging helpers for RKJO observability."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any


def _normalize(
    value: Any,
) -> Any:
    """Convert common Python values to JSON-safe representations."""

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, dict):
        return {
            str(key): _normalize(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            _normalize(item)
            for item in value
        ]

    return value


def build_structured_event(
    event: str,
    **fields: Any,
) -> str:
    """Build one deterministic JSON log event."""

    if not event or not event.strip():
        raise ValueError(
            "Structured log event must not be empty."
        )

    payload = {
        "event": event,
        **{
            key: _normalize(value)
            for key, value in fields.items()
            if value is not None
        },
    }

    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def structured_log(
    logger: logging.Logger,
    *,
    level: int = logging.INFO,
    event: str,
    **fields: Any,
) -> None:
    """Write one structured event through an existing logger."""

    logger.log(
        level,
        build_structured_event(
            event,
            **fields,
        ),
    )
