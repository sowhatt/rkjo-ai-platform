"""Retry policy for asynchronous agent execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """Decision returned by a retry policy."""

    should_retry: bool
    attempt: int
    max_attempts: int
    delay_seconds: float
    reason: str


class RetryPolicy:
    """Deterministic retry policy independent of RabbitMQ."""

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        base_delay_seconds: float = 1.0,
        retryable_exceptions: tuple[type[Exception], ...] = (
            TimeoutError,
            ConnectionError,
        ),
    ) -> None:
        if max_attempts < 1:
            raise ValueError(
                "max_attempts must be greater than or equal to 1."
            )

        if base_delay_seconds < 0:
            raise ValueError(
                "base_delay_seconds must be greater than or equal to 0."
            )

        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds
        self.retryable_exceptions = retryable_exceptions

    def decide(
        self,
        *,
        error: Exception,
        attempt: int,
    ) -> RetryDecision:
        """Return whether the failed execution should be retried."""

        if attempt < 1:
            raise ValueError(
                "attempt must be greater than or equal to 1."
            )

        retryable = isinstance(
            error,
            self.retryable_exceptions,
        )

        if not retryable:
            return RetryDecision(
                should_retry=False,
                attempt=attempt,
                max_attempts=self.max_attempts,
                delay_seconds=0.0,
                reason="permanent_error",
            )

        if attempt >= self.max_attempts:
            return RetryDecision(
                should_retry=False,
                attempt=attempt,
                max_attempts=self.max_attempts,
                delay_seconds=0.0,
                reason="max_attempts_reached",
            )

        delay = self.base_delay_seconds * (
            2 ** (attempt - 1)
        )

        return RetryDecision(
            should_retry=True,
            attempt=attempt,
            max_attempts=self.max_attempts,
            delay_seconds=delay,
            reason="retryable_error",
        )
