import pytest

from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.workflow.agent_routing import (
    WorkflowAgentRouter,
)
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep


def make_router(*descriptors):
    registry = AgentRegistry()

    service = RegistryService(
        registry=registry
    )

    for descriptor in descriptors:
        service.register_agent(
            descriptor
        )

    return WorkflowAgentRouter(
        registry_service=service
    )


def make_descriptor(
    *,
    name,
    queue_name,
    status=AgentStatus.AVAILABLE,
    priority=5,
    capabilities=None,
):
    return AgentDescriptor(
        name=name,
        display_name=name,
        product="ADIP",
        queue_name=queue_name,
        status=status,
        priority=priority,
        capabilities=capabilities or [],
    )


def test_resolve_explicit_agent():
    router = make_router(
        make_descriptor(
            name="weather.agent",
            queue_name="weather.queue",
        )
    )

    step = WorkflowStep(
        step_id="weather",
        name="Weather",
        agent_name="weather.agent",
    )

    route = router.resolve(
        step
    )

    assert route.agent_name == "weather.agent"
    assert route.queue_name == "weather.queue"


def test_unknown_agent_is_rejected():
    router = make_router()

    step = WorkflowStep(
        step_id="weather",
        name="Weather",
        agent_name="unknown.agent",
    )

    with pytest.raises(
        LookupError,
        match="not registered",
    ):
        router.resolve(step)


def test_unavailable_explicit_agent_is_rejected():
    router = make_router(
        make_descriptor(
            name="weather.agent",
            queue_name="weather.queue",
            status=AgentStatus.BUSY,
        )
    )

    step = WorkflowStep(
        step_id="weather",
        name="Weather",
        agent_name="weather.agent",
    )

    with pytest.raises(
        LookupError,
        match="not available",
    ):
        router.resolve(step)


def test_resolve_capability_selects_highest_priority_agent():
    capability = AgentCapability(
        name="weather.analysis",
        description="Weather analysis capability",
    )

    router = make_router(
        make_descriptor(
            name="weather.low",
            queue_name="weather.low.queue",
            priority=3,
            capabilities=[capability],
        ),
        make_descriptor(
            name="weather.high",
            queue_name="weather.high.queue",
            priority=9,
            capabilities=[capability],
        ),
    )

    step = WorkflowStep(
        step_id="weather",
        name="Weather",
        capability_name="weather.analysis",
    )

    route = router.resolve(
        step
    )

    assert route.agent_name == "weather.high"
    assert route.queue_name == (
        "weather.high.queue"
    )


def test_capability_ignores_unavailable_agents():
    capability = AgentCapability(
        name="weather.analysis",
        description="Weather analysis capability",
    )

    router = make_router(
        make_descriptor(
            name="weather.busy",
            queue_name="weather.busy.queue",
            priority=10,
            status=AgentStatus.BUSY,
            capabilities=[capability],
        ),
        make_descriptor(
            name="weather.available",
            queue_name="weather.available.queue",
            priority=5,
            capabilities=[capability],
        ),
    )

    step = WorkflowStep(
        step_id="weather",
        name="Weather",
        capability_name="weather.analysis",
    )

    route = router.resolve(
        step
    )

    assert route.agent_name == (
        "weather.available"
    )


def test_missing_capability_agent_is_rejected():
    router = make_router()

    step = WorkflowStep(
        step_id="weather",
        name="Weather",
        capability_name="weather.analysis",
    )

    with pytest.raises(
        LookupError,
        match="No available agent",
    ):
        router.resolve(step)
