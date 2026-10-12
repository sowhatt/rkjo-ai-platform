from dataclasses import replace

import pytest

from rkjo_education.curriculum.study_audio_workflow import (
    AudioWorkflowAdmission, build_audio_transcription_workflow,
)
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.repository.memory import InMemoryWorkflowRepository


def admission(**kwargs):
    fields = dict(
        tenant_id="university-1", learner_id="student-1",
        source_id="audio-1", source_version=1,
        content_sha256="a" * 64, storage_reference="private://audio/1",
        rights_verified=True, payment_required=True, payment_verified=True,
    )
    fields.update(kwargs)
    return AudioWorkflowAdmission(**fields)


def test_deterministic_idempotency_and_separate_student_identity():
    first = admission()
    assert first.execution_id == admission().execution_id
    assert first.execution_id != replace(first, learner_id="student-2").execution_id
    assert first.execution_id != replace(first, source_version=2).execution_id
    assert first.execution_id != replace(first, content_sha256="b" * 64).execution_id


@pytest.mark.parametrize("override", [
    {"rights_verified": False},
    {"payment_verified": False},
    {"storage_reference": "https://somewhere.invalid/file"},
    {"source_version": 0},
    {"content_sha256": "broken"},
])
def test_workflow_refuses_unsafe_admission(override):
    with pytest.raises(ValueError):
        admission(**override)


def test_definition_runs_on_existing_workflow_engine_without_dispatch():
    data = admission()
    definition = build_audio_transcription_workflow(data)
    repo = InMemoryWorkflowRepository()
    engine = WorkflowEngine(repository=repo)
    execution = engine.create_execution(
        definition,
        execution_id=data.execution_id,
        metadata={
            "tenant_id": data.tenant_id, "learner_id": data.learner_id,
            "source_id": data.source_id, "source_version": data.source_version,
        },
    )
    assert execution.execution_id == data.execution_id
    assert len(definition.steps) == 2
    assert repo.get(execution.execution_id) is not None
    assert definition.steps[0].capability_name == "education.audio.transcribe"
