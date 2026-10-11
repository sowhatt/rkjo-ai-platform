from rkjo_api.security import ApiRole, required_role_for_request


def test_student_preview_uses_viewer_role():
    role = required_role_for_request(
        method="POST", path="/education/study/preview-pdf"
    )
    assert role == ApiRole.VIEWER


def test_general_education_write_still_operator():
    role = required_role_for_request(method="POST", path="/education/courses")
    assert role == ApiRole.OPERATOR
