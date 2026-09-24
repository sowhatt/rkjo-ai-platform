import asyncio
import json
from uuid import UUID, uuid4

import pytest

from rkjo_api.education_supervision import supervision_event_stream
from rkjo_education.events import EducationEventType, EducationLearningEvent
from rkjo_education.supervision import LearnerSupervisionProjection


TENANT_A = UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = UUID("22222222-2222-2222-2222-222222222222")


class DisconnectAfter:
    def __init__(self, checks: int):
        self.checks = checks
        self.calls = 0

    async def is_disconnected(self):
        self.calls += 1
        return self.calls > self.checks


async def collect_chunks(stream, count):
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)
        if len(chunks) >= count:
            break
    return chunks


@pytest.mark.asyncio
async def test_sse_initial_snapshot_is_tenant_scoped():
    projection = LearnerSupervisionProjection()
    learner_a = uuid4()
    learner_b = uuid4()
    projection.apply(EducationLearningEvent(
        event_type=EducationEventType.SESSION_STARTED,
        tenant_id=TENANT_A,
        learner_id=learner_a,
    ))
    projection.apply(EducationLearningEvent(
        event_type=EducationEventType.SESSION_STARTED,
        tenant_id=TENANT_B,
        learner_id=learner_b,
    ))

    async def scenario():\n        return await collect_chunks(
        supervision_event_stream(
            request=DisconnectAfter(1),
            tenant_id=TENANT_A,
            projection=projection,
            poll_interval_seconds=0,
        ),
        2,
    )

    assert chunks[0] == "event: supervision.snapshot\n"
    payload = json.loads(chunks[1].removeprefix("data: ").strip())
    assert {item["learner_id"] for item in payload} == {str(learner_a)}
    assert str(learner_b) not in chunks[1]


@pytest.mark.asyncio
async def test_sse_emits_again_only_after_state_changes():
    projection = LearnerSupervisionProjection()
    learner_id = uuid4()
    projection.apply(EducationLearningEvent(
        event_type=EducationEventType.SESSION_STARTED,
        tenant_id=TENANT_A,
        learner_id=learner_id,
    ))
    request = DisconnectAfter(4)
    stream = supervision_event_stream(
        request=request,
        tenant_id=TENANT_A,
        projection=projection,
        poll_interval_seconds=0,
    )

    first = await anext(stream)
    second = await anext(stream)
    assert first == "event: supervision.snapshot\n"
    assert '"autonomy_score":null' in second

    projection.apply(EducationLearningEvent(
        event_type=EducationEventType.AUTONOMY_UPDATED,
        tenant_id=TENANT_A,
        learner_id=learner_id,
        payload={"score": 91},
    ))

    third = await anext(stream)
    fourth = await anext(stream)
    assert third == "event: supervision.snapshot\n    "
    assert '"autonomy_score":91' in fourth
    await stream.aclose()


\n    first, second, third, fourth = asyncio.run(scenario())\n    assert first == \"event: supervision.snapshot\\n\"\n    assert '\"autonomy_score\":null' in second\n    assert third == \"event: supervision.snapshot\\n\"\n    assert '\"autonomy_score\":91' in fourth\n\ndef test_sse_route_requires_authentication(client):
    response = client.get(
        "/education/supervision/stream",
        headers={"X-API-Key": "invalid"},
    )
    assert response.status_code == 401


def test_sse_route_requires_uuid_tenant(client, monkeypatch):
    monkeypatch.setenv("RKJO_VIEWER_TENANT_ID", "tenant-a")
    response = client.get(
        "/education/supervision/stream",
        headers={"X-API-Key": "rkjo-viewer-key"},
    )
    assert response.status_code == 400
