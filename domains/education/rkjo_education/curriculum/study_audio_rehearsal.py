"""P0.3 synthetic-only, transactional audio workflow rehearsal.

Creates a real persisted WorkflowExecution and outbox entry *atomically* using
the existing RKJO workflow schema. Queue is intentionally a quarantine name:
do not run an OutboxPublisher on this database until ASR capability is real.
No payment, transcription or learner result is claimed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import psycopg

from rkjo_education.curriculum.study_audio_workflow import (
    AudioWorkflowAdmission, build_audio_transcription_workflow,
)
from rkjo_kernel.workflow.models.workflow_execution import WorkflowExecution
from rkjo_kernel.workflow.models.workflow_context import WorkflowContext
from rkjo_kernel.workflow.outbox import OutboxMessage
from rkjo_kernel.workflow.postgres_unit_of_work import PostgreSQLWorkflowUnitOfWork
from rkjo_kernel.workflow.repository.serializer import workflow_execution_to_dict
from rkjo_kernel.workflow.async_dispatch import AsyncWorkflowDispatcher

# This route has no production worker and must not be consumed by a real broker.
REHEARSAL_QUEUE = "rkjo.education.audio.synthetic.rehearsal.disabled"
REHEARSAL_REPLY_QUEUE = "rkjo.education.audio.synthetic.results.disabled"


@dataclass(frozen=True)
class RehearsalResult:
    execution_id: str
    source_id: str
    created: bool
    status: str
    outbox_id: str


class SyntheticAudioRehearsal:
    def __init__(self, database_url: str):
        if not database_url:
            raise ValueError("Dedicated database URL required")
        self.database_url = database_url

    def initialize_schema(self) -> None:
        # Existing kernel owns its workflow, inbox and outbox schemas.
        PostgreSQLWorkflowUnitOfWork(self.database_url).initialize_schema()

    def enqueue(
        self, *, tenant_id: str, learner_id: str, source_id: str,
        dispatcher: AsyncWorkflowDispatcher,
    ) -> RehearsalResult:
        """Atomically insert an unprocessed job plus an unpublished outbox row.

        Restrict to an existing unexpired staged file owned by this student.
        Filename convention is deliberately strict; no production audio enters
        the synthetic rehearsal, even accidentally.
        """
        if not tenant_id or not learner_id:
            raise ValueError("Tenant and learner are mandatory")
        normalized_source_id = str(UUID(source_id))
        with PostgreSQLWorkflowUnitOfWork(self.database_url) as uow:
            conn = uow._connection
            assert conn is not None
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT filename, sha256, state
                    FROM education_staged_audio
                    WHERE source_id=%s::uuid AND tenant_id=%s AND learner_id=%s
                      AND expires_at > now()
                    FOR SHARE
                """, (normalized_source_id, tenant_id, learner_id))
                source = cur.fetchone()
                if source is None:
                    raise LookupError("No accessible staged audio")
                filename, digest, state = source
                if filename != "rkjo-synthetic-lecture.wav" or state != "staged":
                    raise ValueError("Rehearsal accepts synthetic fixture only")

                admission = AudioWorkflowAdmission(
                    tenant_id=tenant_id, learner_id=learner_id,
                    source_id=normalized_source_id, source_version=1,
                    content_sha256=digest,
                    storage_reference=f"private://education-staged-audio/{normalized_source_id}",
                    rights_verified=True,
                    payment_required=False, payment_verified=False,
                )
                definition = build_audio_transcription_workflow(admission)
                execution = WorkflowExecution(
                    definition=definition,
                    execution_id=admission.execution_id,
                    context=WorkflowContext(
                        input_data={"source_id": normalized_source_id},
                        metadata={
                            "tenant_id": tenant_id,
                            "learner_id": learner_id,
                            "synthetic_only": True,
                        },
                    ),
                )
                execution.start()
                first = definition.ordered_steps()[0]
                execution.select_step(first.step_id)
                first.start()
                now = datetime.now(timezone.utc)
                # Never call the kernel upsert for initial admission: concurrent
                # identical submissions must not overwrite an active job.
                cur.execute("""
                    INSERT INTO workflow_executions (
                        execution_id, workflow_id, status, payload,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT (execution_id) DO NOTHING
                    RETURNING execution_id
                """, (
                    execution.execution_id, definition.workflow_id,
                    execution.status.value,
                    json.dumps(workflow_execution_to_dict(execution)),
                    now, now,
                ))
                created = cur.fetchone() is not None
                outbox_id = f"edu-audio-synthetic-{admission.execution_id}"
                if created:
                    queue, message = dispatcher.prepare(
                        step=first, context=execution.context,
                        queue_name=REHEARSAL_QUEUE,
                        execution_id=execution.execution_id,
                        correlation_id=execution.execution_id,
                        reply_queue=REHEARSAL_REPLY_QUEUE,
                    )
                    uow.outbox.add(OutboxMessage(
                        outbox_id=outbox_id, queue_name=queue,
                        message=message, created_at=now,
                    ))
                else:
                    # No overwrite or repeated outbox insert. If an existing
                    # workflow belongs to another owner, fail closed.
                    cur.execute(
                        "SELECT payload FROM workflow_executions WHERE execution_id=%s",
                        (execution.execution_id,),
                    )
                    old = cur.fetchone()
                    if not old:
                        raise RuntimeError("Existing workflow not found")
                    meta = old[0].get("context", {}).get("metadata", {})
                    if meta.get("tenant_id") != tenant_id or meta.get("learner_id") != learner_id:
                        raise PermissionError("Workflow ownership mismatch")
                uow.commit()
        return RehearsalResult(
            execution_id=execution.execution_id,
            source_id=normalized_source_id,
            created=created,
            status="running" if created else "existing",
            outbox_id=outbox_id,
        )
