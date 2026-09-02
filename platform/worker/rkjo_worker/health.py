"""Health state for RKJO worker services."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class WorkerHealthSnapshot:
    """Immutable snapshot of a worker service health state."""

    service_name: str
    live: bool
    ready: bool
    status: str
    last_error: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "service_name": self.service_name,
            "live": self.live,
            "ready": self.ready,
            "status": self.status,
            "last_error": self.last_error,
        }


class WorkerHealth:
    """Thread-safe lifecycle health state for a worker service."""

    def __init__(
        self,
        service_name: str,
    ) -> None:
        if not service_name.strip():
            raise ValueError(
                "service_name must not be empty."
            )

        self.service_name = service_name
        self._live = True
        self._ready = False
        self._last_error: str | None = None
        self._lock = Lock()

    def mark_ready(self) -> None:
        with self._lock:
            if not self._live:
                return

            self._ready = True
            self._last_error = None

    def mark_not_ready(
        self,
        error: Exception | str | None = None,
    ) -> None:
        with self._lock:
            self._ready = False
            self._last_error = (
                str(error)
                if error is not None
                else None
            )

    def mark_stopped(self) -> None:
        with self._lock:
            self._live = False
            self._ready = False

    def snapshot(self) -> WorkerHealthSnapshot:
        with self._lock:
            live = self._live
            ready = self._ready
            last_error = self._last_error

        if not live:
            status = "stopped"
        elif ready:
            status = "ready"
        else:
            status = "not_ready"

        return WorkerHealthSnapshot(
            service_name=self.service_name,
            live=live,
            ready=ready,
            status=status,
            last_error=last_error,
        )
