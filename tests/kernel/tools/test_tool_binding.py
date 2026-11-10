import pytest
from pydantic import ValidationError

from rkjo_kernel.tools.binding import ToolBinding


def test_tool_binding_normalizes_names():
    binding = ToolBinding(
        capability_name=" Course_Search ",
        tool_name=" Education.Search_Course ",
    )

    assert binding.capability_name == "course_search"
    assert binding.tool_name == "education.search_course"


def test_tool_binding_rejects_empty_capability():
    with pytest.raises(ValidationError):
        ToolBinding(
            capability_name=" ",
            tool_name="education.search_course",
        )


def test_tool_binding_rejects_empty_tool():
    with pytest.raises(ValidationError):
        ToolBinding(
            capability_name="course_search",
            tool_name=" ",
        )
