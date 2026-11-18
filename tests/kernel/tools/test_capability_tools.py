import pytest
from pydantic import ValidationError

from rkjo_kernel.registry.capability import AgentCapability


def test_capability_accepts_declared_tools():
    capability = AgentCapability(
        name="course_search",
        description="Search education courses.",
        tools=[
            " Education.Search_Course ",
            "education.get_course",
        ],
    )

    assert capability.tools == [
        "education.search_course",
        "education.get_course",
    ]


def test_capability_tools_default_empty():
    capability = AgentCapability(
        name="course_search",
        description="Search education courses.",
    )

    assert capability.tools == []


def test_capability_rejects_empty_tool_name():
    with pytest.raises(ValidationError):
        AgentCapability(
            name="course_search",
            description="Search education courses.",
            tools=[" "],
        )


def test_capability_rejects_tool_name_with_spaces():
    with pytest.raises(ValidationError):
        AgentCapability(
            name="course_search",
            description="Search education courses.",
            tools=["education search course"],
        )


def test_capability_deduplicates_tools_preserving_order():
    capability = AgentCapability(
        name="course_search",
        description="Search education courses.",
        tools=[
            "education.search_course",
            "education.get_course",
            "education.search_course",
        ],
    )

    assert capability.tools == [
        "education.search_course",
        "education.get_course",
    ]
