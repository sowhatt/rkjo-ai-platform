import pytest

from rkjo_kernel.runtime.retry_policy import (
    RetryPolicy,
)


def test_retryable_error_is_retried():
    policy = RetryPolicy(
        max_attempts=3,
        base_delay_seconds=1.0,
    )

    decision = policy.decide(
        error=TimeoutError("timeout"),
        attempt=1,
    )

    assert decision.should_retry is True
    assert decision.attempt == 1
    assert decision.max_attempts == 3
    assert decision.delay_seconds == 1.0
    assert decision.reason == "retryable_error"


def test_exponential_backoff_is_applied():
    policy = RetryPolicy(
        max_attempts=5,
        base_delay_seconds=2.0,
    )

    first = policy.decide(
        error=ConnectionError("network"),
        attempt=1,
    )

    second = policy.decide(
        error=ConnectionError("network"),
        attempt=2,
    )

    third = policy.decide(
        error=ConnectionError("network"),
        attempt=3,
    )

    assert first.delay_seconds == 2.0
    assert second.delay_seconds == 4.0
    assert third.delay_seconds == 8.0


def test_permanent_error_is_not_retried():
    policy = RetryPolicy()

    decision = policy.decide(
        error=ValueError("invalid payload"),
        attempt=1,
    )

    assert decision.should_retry is False
    assert decision.delay_seconds == 0.0
    assert decision.reason == "permanent_error"


def test_retry_stops_at_max_attempts():
    policy = RetryPolicy(
        max_attempts=3,
    )

    decision = policy.decide(
        error=TimeoutError("timeout"),
        attempt=3,
    )

    assert decision.should_retry is False
    assert decision.reason == (
        "max_attempts_reached"
    )


def test_custom_retryable_exception():
    class TemporaryProviderError(Exception):
        pass

    policy = RetryPolicy(
        retryable_exceptions=(
            TemporaryProviderError,
        ),
    )

    decision = policy.decide(
        error=TemporaryProviderError(
            "provider unavailable"
        ),
        attempt=1,
    )

    assert decision.should_retry is True


def test_invalid_max_attempts_is_rejected():
    with pytest.raises(
        ValueError,
        match="max_attempts",
    ):
        RetryPolicy(
            max_attempts=0
        )


def test_negative_delay_is_rejected():
    with pytest.raises(
        ValueError,
        match="base_delay_seconds",
    ):
        RetryPolicy(
            base_delay_seconds=-1
        )


def test_invalid_attempt_is_rejected():
    policy = RetryPolicy()

    with pytest.raises(
        ValueError,
        match="attempt",
    ):
        policy.decide(
            error=TimeoutError(),
            attempt=0,
        )
