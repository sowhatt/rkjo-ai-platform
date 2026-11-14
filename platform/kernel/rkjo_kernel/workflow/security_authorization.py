"""Workflow admission against server-owned state and durable dispatch intents.

Adapted from S1 WorkflowAuthorization: retain consolidation's dual metadata,
capability routing and canonical result queue. Dynamic grant revocation is a
separate concern. SQL and the result-signing key belong to trusted services.
"""
from contextlib import contextmanager
import hashlib
import hmac
import json
import os

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.runtime.result_publisher import _result_metadata


class WorkflowAdmissionDenied(PermissionError):
    """An untrusted message must not produce an agent effect or failure result."""


class ResultAuthenticator:
    """Authenticate the whole result envelope, including payload and source."""

    def __init__(self, key: str):
        if len(key.encode()) < 32:
            raise ValueError("Workflow result key must contain at least 32 bytes.")
        self._key = key.encode()

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("RKJO_WORKFLOW_RESULT_SECRET", ""))

    def _digest(self, message):
        envelope = message.model_dump(mode="json")
        envelope["metadata"].pop("result_signature", None)
        body = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hmac.new(self._key, body.encode(), hashlib.sha256).hexdigest()

    def sign(self, message):
        message.metadata["result_signature"] = self._digest(message)

    def verify(self, message):
        signature = message.metadata.get("result_signature")
        if not isinstance(signature, str) or not hmac.compare_digest(signature, self._digest(message)):
            raise WorkflowAdmissionDenied("Unauthenticated workflow result.")


class WorkflowAuthorization:
    def __init__(self, *, uow_factory, reply_queue, authenticator=None):
        self.uow_factory = uow_factory
        self.reply_queue = reply_queue
        self.authenticator = authenticator

    @staticmethod
    def _owned(execution):
        if execution is None:
            raise WorkflowAdmissionDenied("Workflow unavailable.")
        meta = execution.context.metadata
        if (any(not isinstance(meta.get(k), str) or not meta[k].strip()
                for k in ("tenant_id", "user_id", "mission_id", "trace_id", "request_id"))
                or meta != execution.metadata
                or meta.get("policy_context", {}).get("api_role") not in {"operator", "admin"}):
            raise WorkflowAdmissionDenied("Workflow authority unavailable; explicit migration required.")
        return meta

    def _request(self, uow, execution, identifier):
        meta = self._owned(execution)
        intent = uow.outbox.get(identifier)
        if intent is None:
            raise WorkflowAdmissionDenied("Unknown durable dispatch.")
        request = intent.message
        step = next((s for s in execution.definition.steps
                     if s.step_id == request.metadata.get("workflow_step_id")), None)
        if (step is None or request.source != "rkjo.workflow"
                or request.message_type != "workflow.step.execute"
                or request.metadata.get("workflow_execution_id") != execution.execution_id
                or request.metadata.get("reply_queue") != self.reply_queue
                or request.metadata.get("capability_name") != step.capability_name
                or (step.agent_name and step.agent_name != request.target)
                or any(request.metadata.get(k) != v for k, v in meta.items())):
            raise WorkflowAdmissionDenied("Dispatch authority mismatch.")
        return request, step

    @contextmanager
    def admit(self, message, agent_name):
        # The row lock serializes admission with workflow transitions. No
        # untrusted fields are applied to persisted ownership or agent context.
        with self.uow_factory() as uow:
            execution = uow.workflows.get(message.metadata.get("workflow_execution_id"))
            request, step = self._request(uow, execution, message.message_id)
            if message != request or message.target != agent_name:
                raise WorkflowAdmissionDenied("Workflow request mismatch.")
            if step.status.value in {"completed", "failed"}:
                yield False  # ACK a genuine old request without another effect.
                return
            if (execution.status.value != "running" or execution.current_step_id != step.step_id
                    or message.payload != {"input_data": execution.context.input_data,
                                           "variables": execution.context.variables,
                                           "outputs": execution.context.outputs}):
                raise WorkflowAdmissionDenied("Workflow step unavailable.")
            yield True

    def authorize_result(self, uow, execution, message):
        if self.authenticator is None:
            raise WorkflowAdmissionDenied("Result authenticator required.")
        self.authenticator.verify(message)
        request, _ = self._request(uow, execution, message.metadata.get("request_message_id"))
        metadata = dict(message.metadata)
        metadata.pop("result_signature", None)
        if (message.source != request.target or message.target != "rkjo.workflow"
                or message.correlation_id != request.correlation_id
                or metadata != _result_metadata(request)
                or type(message.payload.get("success")) is not bool):
            raise WorkflowAdmissionDenied("Workflow result authority mismatch.")
