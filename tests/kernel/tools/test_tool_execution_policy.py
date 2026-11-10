import pytest

from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.policy import (
    ToolExecutionDecision,
    ToolExecutionPolicy,
)


def build_context(
    *,
    agent_name: str = "education.agent",
    capability_name: str = "course_search",
) -> ToolExecutionContext:
    return ToolExecutionContext(
        tenant_id="tenant.demo",
        agent_name=agent_name,
        capability_name=capability_name,
    )


def test_policy_allows_declared_tool():
    capability = AgentCapability(
        name="course_search",
        description="Search education courses.",
        tools=[
            "education.search_course",
            "education.get_course",
        ],
    )

    decision = ToolExecutionPolicy().evaluate(
        capability=capability,
        tool_name="education.search_course",
        context=build_context(),
    )

    assert decision == ToolExecutionDecision.ALLOW


def test_policy_denies_undeclared_tool():
    capability = AgentCapability(
        name="course_search",
        description="Search education courses.",
        tools=["education.search_course"],
    )

    decision = ToolExecutionPolicy().evaluate(
        capability=capability,
        tool_name="education.delete_course",
        context=build_context(),
    )

    assert decision == ToolExecutionDecision.DENY


def test_policy_denies_capability_context_mismatch():
    capability = AgentCapability(
        name="course_search",
        description="Search education courses.",
        tools=["education.search_course"],
    )

    decision = ToolExecutionPolicy().evaluate(
        capability=capability,
        tool_name="education.search_course",
        context=build_context(
            capability_name="student_management"
        ),
    )

    assert decision == ToolExecutionDecision.DENY


def test_policy_normalizes_tool_name():
    capability = AgentCapability(
        name="course_search",
        description="Search education courses.",
        tools=["education.search_course"],
    )

    decision = ToolExecutionPolicy().evaluate(
        capability=capability,
        tool_name=" EDUCATION.SEARCH_COURSE ",
        context=build_context(),
    )

    assert decision == ToolExecutionDecision.ALLOW


def test_policy_rejects_empty_tool_name():
    capability = AgentCapability(
        name="course_search",
        description="Search education courses.",
    )

    with pytest.raises(ValueError):
        ToolExecutionPolicy().evaluate(
            capability=capability,
            tool_name=" ",
            context=build_context(),
        )
