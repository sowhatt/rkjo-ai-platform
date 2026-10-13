from rkjo_api.security import ApiRole, required_role_for_request


def test_student_write_viewer_paths():
    assert required_role_for_request(method="POST", path="/education/attempts") == ApiRole.VIEWER
    assert required_role_for_request(method="POST", path="/education/attempts/a/submit") == ApiRole.VIEWER
    assert required_role_for_request(method="POST", path="/education/proof-challenges/a/submit") == ApiRole.VIEWER


def test_admin_education_writes_still_operator():
    assert required_role_for_request(method="POST", path="/education/assessments") == ApiRole.OPERATOR
    assert required_role_for_request(method="POST", path="/education/progress") == ApiRole.OPERATOR
