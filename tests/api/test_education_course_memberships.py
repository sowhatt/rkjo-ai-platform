"""MM-RAG-03.4 course membership-backed API permissions."""
import pytest

from rkjo_api.dependencies import (
    get_education_course_service, get_education_course_access, get_rag_answering_service,
)
from rkjo_api.jwt_auth import create_access_token
from rkjo_api.main import app
from rkjo_api.security import ApiRole
from rkjo_education.course.membership import CourseAccess, CourseMemberRole, CourseMembership
from rkjo_kernel.rag.generation_models import RAGAnswer, AnswerSource


class MembershipRepo:
    def __init__(self):
        self.members = {}

    def get(self, *, tenant_id, course_id, subject):
        return self.members.get((tenant_id, course_id, subject))

    def upsert(self, member):
        self.members[(member.tenant_id, member.course_id, member.subject)] = member
        return member


class Courses:
    document_ids = ["doc-one"]

    def get(self, *, tenant_id, course_id):
        if tenant_id != "tenant-a" or course_id != "course-one":
            raise LookupError("Course missing")
        return self


class Answer:
    def __init__(self):
        self.calls = []
    def answer(self, question, *, limit, filters):
        self.calls.append(filters.metadata)
        return RAGAnswer(
            answer="Optique 250 euros [1].", sanitized_query=question,
            sources=[AnswerSource(
                citation=1, document_id="doc-one", chunk_id="chunk-1",
                score=0.9, page_number=1,
            )],
        )


@pytest.fixture
def wired():
    repo = MembershipRepo()
    answer = Answer()
    app.dependency_overrides[get_education_course_service] = lambda: Courses()
    app.dependency_overrides[get_education_course_access] = lambda: CourseAccess(repo)
    app.dependency_overrides[get_rag_answering_service] = lambda: answer
    yield repo, answer
    for dep in (
        get_education_course_service,
        get_education_course_access,
        get_rag_answering_service,
    ):
        app.dependency_overrides.pop(dep, None)


def token(subject, role, tenant="tenant-a"):
    return {"Authorization": "Bearer " + create_access_token(
        subject=subject, role=role, tenant_id=tenant,
    )}


def ask(client, headers, doc="doc-one"):
    return client.post(
        "/education/courses/course-one/learner-answer", headers=headers,
        json={"question": "Quelle garantie ?", "document_id": doc},
    )


def test_unenrolled_learner_is_denied(client, wired):
    response = ask(client, token("learner-1", ApiRole.VIEWER))
    assert response.status_code == 403
    assert wired[1].calls == []


def test_admin_enrolls_then_learner_can_answer(client, wired):
    enrollment = client.post(
        "/education/courses/course-one/members",
        headers=token("admin-1", ApiRole.ADMIN),
        json={"subject": "learner-1", "role": "learner"},
    )
    assert enrollment.status_code == 200, enrollment.text
    assert enrollment.json()["role"] == "learner"
    response = ask(client, token("learner-1", ApiRole.VIEWER))
    assert response.status_code == 200, response.text
    assert response.json()["sources"][0]["page_number"] == 1
    assert wired[1].calls == [{"tenant_id": "tenant-a", "evidence_document_id": "doc-one"}]


def test_cross_tenant_membership_cannot_be_reused(client, wired):
    wired[0].upsert(CourseMembership(
        "tenant-a", "course-one", "learner-1", CourseMemberRole.LEARNER,
    ))
    response = ask(client, token("learner-1", ApiRole.VIEWER, tenant="tenant-b"))
    assert response.status_code == 403
    assert wired[1].calls == []


def test_unattached_document_denied_without_generation(client, wired):
    wired[0].upsert(CourseMembership(
        "tenant-a", "course-one", "learner-1", CourseMemberRole.LEARNER,
    ))
    assert ask(client, token("learner-1", ApiRole.VIEWER), "unrelated").status_code == 404
    assert wired[1].calls == []


def test_anonymous_api_key_cannot_enroll(client, wired):
    response = client.post(
        "/education/courses/course-one/members",
        headers={"X-API-Key": "rkjo-admin-key"},
        json={"subject": "learner-1", "role": "learner"},
    )
    assert response.status_code == 403


def test_learner_cannot_enroll_other_people(client, wired):
    response = client.post(
        "/education/courses/course-one/members",
        headers=token("learner-1", ApiRole.VIEWER),
        json={"subject": "another", "role": "teacher"},
    )
    assert response.status_code == 403
