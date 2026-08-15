import json
import logging
from datetime import datetime, timezone

import pytest

from rkjo_kernel.logging.structured import (
    build_structured_event,
    structured_log,
)


def test_build_structured_event_returns_json():
    result = build_structured_event(
        "workflow.dispatched",
        execution_id="exec-001",
        correlation_id="corr-001",
    )

    payload = json.loads(result)

    assert payload == {
        "correlation_id": "corr-001",
        "event": "workflow.dispatched",
        "execution_id": "exec-001",
    }


def test_none_fields_are_omitted():
    result = build_structured_event(
        "workflow.created",
        execution_id="exec-001",
        error=None,
    )

    payload = json.loads(result)

    assert "error" not in payload


def test_datetime_is_serialized():
    timestamp = datetime(
        2026,
        8,
        15,
        10,
        0,
        tzinfo=timezone.utc,
    )

    result = build_structured_event(
        "test.event",
        timestamp=timestamp,
    )

    payload = json.loads(result)

    assert payload["timestamp"] == (
        timestamp.isoformat()
    )


def test_empty_event_is_rejected():
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        build_structured_event(
            " "
        )


def test_structured_log_uses_logger():
    class FakeLogger:
        def __init__(self):
            self.calls = []

        def log(
            self,
            level,
            message,
        ):
            self.calls.append(
                (level, message)
            )

    logger = FakeLogger()

    structured_log(
        logger,
        level=logging.WARNING,
        event="runtime.retry",
        correlation_id="corr-001",
    )

    assert len(logger.calls) == 1

    level, message = logger.calls[0]

    assert level == logging.WARNING

    payload = json.loads(message)

    assert payload["event"] == (
        "runtime.retry"
    )

    assert payload[
        "correlation_id"
    ] == "corr-001"
