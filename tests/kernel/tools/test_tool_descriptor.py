import pytest
from pydantic import ValidationError

from rkjo_kernel.tools.descriptor import ToolDescriptor


def test_tool_descriptor_normalizes_name():
    descriptor = ToolDescriptor(
        name=" Education.Search_Course ",
        display_name="Search course",
        description="Search an education course.",
    )

    assert descriptor.name == "education.search_course"


def test_tool_descriptor_rejects_spaces_in_name():
    with pytest.raises(ValidationError):
        ToolDescriptor(
            name="education search course",
            display_name="Search course",
            description="Search an education course.",
        )


def test_tool_descriptor_rejects_negative_timeout():
    with pytest.raises(ValidationError):
        ToolDescriptor(
            name="education.search_course",
            display_name="Search course",
            description="Search an education course.",
            timeout_ms=-1,
        )
