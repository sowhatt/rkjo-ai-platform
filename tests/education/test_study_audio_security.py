from rkjo_api.security import ApiRole, required_role_for_request


def test_student_audio_inspection_allows_viewer_role():
    assert required_role_for_request(
        method="POST", path="/education/study/inspect-audio"
    ) is ApiRole.VIEWER


def test_other_education_mutation_still_requires_operator():
    assert required_role_for_request(
        method="POST", path="/education/courses"
    ) is ApiRole.OPERATOR
