"""In-memory metrics registry for RKJO observability."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock


class MetricsRegistry:
    """Thread-safe in-memory counter registry."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._lock = Lock()

    def increment(
        self,
        name: str,
        value: int = 1,
    ) -> None:
        if not name or not name.strip():
            raise ValueError(
                "Metric name must not be empty."
            )

        if value < 0:
            raise ValueError(
                "Metric increment must not be negative."
            )

        with self._lock:
            self._counters[name] += value

    def get(
        self,
        name: str,
    ) -> int:
        with self._lock:
            return self._counters.get(name, 0)

    def snapshot(
        self,
    ) -> dict[str, int]:
        with self._lock:
            return dict(self._counters)

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
