"""Standard result returned by an agent execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(slots=True)
class ExecutionResult:
    """Describe the outcome of one agent execution."""

    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: float | None = None

    def __post_init__(self) -> None:
        """Validate result consistency."""
        if self.success and self.error is not None:
            raise ValueError(
                "A successful execution result cannot contain an error."
            )

        if not self.success:
            if self.error is None or not self.error.strip():
                raise ValueError(
                    "A failed execution result requires an error message."
                )

        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError(
                "Execution duration cannot be negative."
            )

    @property
    def is_failure(self) -> bool:
        """Return whether the execution failed."""
        return not self.success

    @classmethod
    def succeeded(
        cls,
        *,
        output: Any = None,
        metadata: Mapping[str, Any] | None = None,
        duration_ms: float | None = None,
    ) -> ExecutionResult:
        """Create a successful execution result."""
        return cls(
            success=True,
            output=output,
            metadata=dict(metadata or {}),
            duration_ms=duration_ms,
        )

    @classmethod
    def failed(
        cls,
        *,
        error: str,
        output: Any = None,
        metadata: Mapping[str, Any] | None = None,
        duration_ms: float | None = None,
    ) -> ExecutionResult:
        """Create a failed execution result."""
        return cls(
            success=False,
            output=output,
            error=error,
            metadata=dict(metadata or {}),
            duration_ms=duration_ms,
        )
