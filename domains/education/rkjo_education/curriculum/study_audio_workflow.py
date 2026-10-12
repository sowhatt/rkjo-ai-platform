"""P0.2 audio orchestration contract for the existing RKJO WorkflowEngine.

This creates a validated *definition* only. A durable job must not be created
until audio bytes have been persisted to an approved private object store,
the student has accepted a quote, and payment is verified when required.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID, uuid5

from rkjo_kernel.workflow.models.workflow_definition import WorkflowDefinition
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep

AUDIO_WORKFLOW_VERSION = "0.1.0"
# Namespace is local to this contract, not a student identity.
_NAMESPACE = UUID("0e32633e-dfca-4ce9-a501-c7076f283659")


@dataclass(frozen=True, slots=True)
class AudioWorkflowAdmission:
    tenant_id: str
    learner_id: str
    source_id: str
    source_version: int
    content_sha256: str
    storage_reference: str
    rights_verified: bool
    payment_required: bool
    payment_verified: bool

    def __post_init__(self) -> None:
        for key in ("tenant_id", "learner_id", "source_id", "storage_reference"):
            if not getattr(self, key).strip():
                raise ValueError(f"{key} required")
        if self.source_version < 1:
            raise ValueError("source_version must be positive")
        if len(self.content_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.content_sha256):
            raise ValueError("content_sha256 must be lowercase hexadecimal SHA-256")
        if not self.storage_reference.startswith("private://"):
            raise ValueError("Only a verified private storage reference is accepted")
        if not self.rights_verified:
            raise ValueError("Rights must be verified before workflow admission")
        if self.payment_required and not self.payment_verified:
            raise ValueError("Payment confirmation required before a paid job")

    @property
    def idempotency_key(self) -> str:
        # Include the version, ownership and operation to avoid cross-user collisions.
        payload = "|".join((
            self.tenant_id, self.learner_id, self.source_id,
            str(self.source_version), self.content_sha256, "audio_transcription",
        ))
        return sha256(payload.encode("utf-8")).hexdigest()

    @property
    def execution_id(self) -> str:
        return str(uuid5(_NAMESPACE, self.idempotency_key))


def build_audio_transcription_workflow(admission: AudioWorkflowAdmission) -> WorkflowDefinition:
    """Build a routable definition. Do not invoke dispatch or impersonate a worker."""
    return WorkflowDefinition(
        workflow_id="education.audio.transcription",
        name="Education Lecture Transcription",
        version=AUDIO_WORKFLOW_VERSION,
        description="Transcribe stored audio with source-aligned timestamps and review before publishing",
        steps=[
            WorkflowStep(
                step_id="transcribe_audio", name="Audio transcription",
                capability_name="education.audio.transcribe",
                position=0,
            ),
            WorkflowStep(
                step_id="validate_transcript", name="Transcript quality gate",
                capability_name="education.audio.review",
                position=1,
            ),
        ],
    )
