from rkjo_kernel.registry.descriptor import AgentStatus
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_worker.agent_catalog import (
    build_platform_worker_descriptor,
    register_platform_worker,
)


def test_build_platform_worker_descriptor(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "RKJO_WORKER_AGENT_NAME",
        "rkjo.catalog.worker",
    )
    monkeypatch.setenv(
        "RKJO_WORKER_QUEUE",
        "rkjo.catalog.queue",
    )
    monkeypatch.setenv(
        "RKJO_WORKER_CAPABILITY",
        "document_analysis",
    )

    descriptor = build_platform_worker_descriptor(
        status=AgentStatus.AVAILABLE,
    )

    assert descriptor.name == "rkjo.catalog.worker"
    assert descriptor.queue_name == "rkjo.catalog.queue"
    assert descriptor.status == AgentStatus.AVAILABLE
    assert descriptor.has_capability(
        "document_analysis"
    )


def test_register_platform_worker(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "RKJO_WORKER_AGENT_NAME",
        "rkjo.catalog.worker",
    )

    registry_service = RegistryService(
        registry=AgentRegistry()
    )

    descriptor = register_platform_worker(
        registry_service,
        status=AgentStatus.AVAILABLE,
    )

    registered = registry_service.get_agent(
        descriptor.name
    )

    assert registered is not None
    assert registered.status == AgentStatus.AVAILABLE
