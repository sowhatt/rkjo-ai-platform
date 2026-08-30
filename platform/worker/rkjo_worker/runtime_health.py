"""Health adapter for the platform AgentRuntime."""

from __future__ import annotations

from rkjo_kernel.runtime.agent_runtime import AgentRuntime
from rkjo_kernel.runtime.status import RuntimeStatus

from rkjo_worker.health import WorkerHealthSnapshot


class RuntimeHealthAdapter:
    """Expose AgentRuntime lifecycle through the worker health contract.

    The adapter is intentionally read-only. It never calls the EventBus and
    therefore remains safe to query from a health HTTP server thread while
    RabbitMQ consumption runs on the main worker thread.
    """

    def __init__(
        self,
        runtime: AgentRuntime,
        service_name: str = "platform-worker",
    ) -> None:
        if not service_name.strip():
            raise ValueError("service_name must not be empty.")

        self.runtime = runtime
        self.service_name = service_name

    def snapshot(self) -> WorkerHealthSnapshot:
        runtime_status = self.runtime.status

        if runtime_status == RuntimeStatus.RUNNING:
            live = True
            ready = True
            status = "ready"

        elif runtime_status == RuntimeStatus.STOPPED:
            live = False
            ready = False
            status = "stopped"

        else:
            live = True
            ready = False
            status = "not_ready"

        return WorkerHealthSnapshot(
            service_name=self.service_name,
            live=live,
            ready=ready,
            status=status,
            last_error=self.runtime.last_error,
        )
