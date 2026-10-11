"""HTTP study provider tests use an in-memory HTTP transport, never real API calls."""
import json

import httpx
import pytest

from rkjo_education.curriculum.health_artifact_pipeline import (
    StudyGenerationError, generate_study_artifact,
)
from rkjo_education.curriculum.http_study_provider import (
    HTTPStudyProvider, StudyHTTPConfig,
)
from rkjo_education.curriculum.study_artifacts import StudyArtifactType
from rkjo_education.curriculum.study_sources import (
    StudyDocumentType, StudySegment, StudySourcePackage,
)


def study_source():
    segment = StudySegment.from_text(
        document_id="cm-cardio", page=3, text="Le coeur comprend quatre cavites."
    )
    return StudySourcePackage(
        tenant_id="university-1", learner_id="student-1",
        programme_id="medicine-year-1", ue_id="physiology",
        document_id="cm-cardio", version=1, document_type=StudyDocumentType.CM,
        segments=(segment,),
    )


def provider(handler):
    transport = httpx.MockTransport(handler)
    factory = lambda **kwargs: httpx.Client(transport=transport, **kwargs)
    return HTTPStudyProvider(
        StudyHTTPConfig(
            endpoint="https://model.example.test/v1/chat/completions",
            api_key="test-only-key", model="test-model"
        ),
        client_factory=factory,
    )


def test_real_http_adapter_contract_and_source_validation():
    source = study_source()
    seen = []

    def handler(request):
        assert request.headers["authorization"] == "Bearer test-only-key"
        body = json.loads(request.content)
        seen.append(body)
        payload = {"items": [{
            "title": "Révision",
            "body": "Quatre cavités selon le document.",
            "segment_ids": [source.segments[0].segment_id],
        }]}
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(payload)}}],
        })

    artifact = generate_study_artifact(
        source=source, track="medicine",
        artifact_type=StudyArtifactType.REVISION_NOTE, provider=provider(handler)
    )
    assert artifact.items[0].segment_ids == (source.segments[0].segment_id,)
    assert seen[0]["model"] == "test-model"
    assert "source_segments" in seen[0]["messages"][1]["content"]


def test_adapter_rejects_fabricated_references():
    def handler(_request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps({
                "items": [{"title": "Fake", "body": "Fake", "segment_ids": ["not-in-PDF"]}]
            })}}],
        })
    with pytest.raises(ValueError, match="Unverifiable"):
        generate_study_artifact(
            source=study_source(), track="pharmacy",
            artifact_type=StudyArtifactType.QUIZ, provider=provider(handler)
        )


@pytest.mark.parametrize("endpoint", [
    "http://model.example.test/v1/chat/completions",
    "file:///tmp/model",
    "https://name:password@model.example.test/api",
])
def test_rejects_unsafe_endpoints(endpoint):
    with pytest.raises(ValueError, match="HTTPS"):
        StudyHTTPConfig(endpoint=endpoint, api_key="key", model="model")


def test_provider_http_errors_are_not_exposed():
    def handler(_request):
        return httpx.Response(503, text="secret server detail")
    with pytest.raises(StudyGenerationError, match="request or JSON response failed"):
        generate_study_artifact(
            source=study_source(), track="nursing",
            artifact_type=StudyArtifactType.MIND_MAP, provider=provider(handler)
        )
