"""MM-RAG-03.3 course-scoped answering safety."""
import pytest
from rkjo_api.main import app
from rkjo_api.dependencies import get_education_course_service, get_rag_answering_service
from rkjo_kernel.rag.generation_models import RAGAnswer, AnswerSource


class Courses:
    def __init__(self, documents=("doc-allowed",), exists=True):
        self.document_ids = list(documents)
        self.exists = exists

    def get(self, *, tenant_id, course_id):
        assert tenant_id == "tenant-a"
        if not self.exists:
            raise LookupError("No course")
        return self


class Answers:
    def __init__(self, wrong_source=False):
        self.calls = []
        self.wrong_source = wrong_source

    def answer(self, question, *, limit, filters):
        self.calls.append(filters.metadata)
        return RAGAnswer(
            answer="Optique : 250 euros [1].",
            sanitized_query=question,
            sources=[AnswerSource(
                citation=1, document_id="other-document" if self.wrong_source else "doc-allowed",
                chunk_id="chunk-p1", score=0.9, page_number=1,
            )],
        )


@pytest.fixture
def wired():
    course = Courses()
    answer = Answers()
    app.dependency_overrides[get_education_course_service] = lambda: course
    app.dependency_overrides[get_rag_answering_service] = lambda: answer
    yield course, answer
    app.dependency_overrides.pop(get_education_course_service, None)
    app.dependency_overrides.pop(get_rag_answering_service, None)


def call(client, *, key="rkjo-operator-key", document_id="doc-allowed"):
    return client.post(
        "/education/courses/course-1/answer",
        headers={"X-API-Key": key},
        json={"question": "Garantie optique ?", "document_id": document_id},
    )


def test_course_answer_is_scoped_and_cites_page(client, wired):
    response = call(client)
    assert response.status_code == 200, response.text
    assert wired[1].calls == [{"tenant_id": "tenant-a", "evidence_document_id": "doc-allowed"}]
    assert response.json()["sources"][0]["page_number"] == 1


def test_course_answer_requires_operator(client, wired):
    assert call(client, key="rkjo-viewer-key").status_code == 403
    assert wired[1].calls == []


def test_course_answer_requires_tenant(client, wired, monkeypatch):
    monkeypatch.delenv("RKJO_OPERATOR_TENANT_ID", raising=False)
    assert call(client).status_code == 403
    assert wired[1].calls == []


def test_course_answer_disallows_unattached_document(client, wired):
    assert call(client, document_id="another-doc").status_code == 404
    assert wired[1].calls == []


def test_course_answer_disallows_missing_course(client, wired):
    wired[0].exists = False
    assert call(client).status_code == 404
    assert wired[1].calls == []


def test_course_answer_refuses_wrong_source_even_if_adapter_leaks(client, wired):
    wired[1].wrong_source = True
    assert call(client).status_code == 502


def test_course_answer_rejects_empty_question(client, wired):
    response = client.post(
        "/education/courses/course-1/answer",
        headers={"X-API-Key": "rkjo-operator-key"},
        json={"question": "", "document_id": "doc-allowed"},
    )
    assert response.status_code == 422
