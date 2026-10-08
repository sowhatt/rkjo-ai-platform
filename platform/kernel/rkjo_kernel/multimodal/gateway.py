"""Provider-neutral ingestion contracts; no framework, queue or storage side effects."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol
from uuid import uuid4

from rkjo_kernel.artifacts.models import ArtifactModality


class ProcessingMode(str, Enum):
    SYNC = "sync"
    ASYNC = "async"


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    tenant_id: str
    subject_id: str

    def __post_init__(self) -> None:
        if not self.tenant_id.strip() or not self.subject_id.strip():
            raise ValueError("Authenticated tenant and subject are required.")


@dataclass(frozen=True, slots=True)
class ChannelContext:
    channel: str
    recipient_ref: str
    correlation_id: str

    def __post_init__(self) -> None:
        if not all((self.channel.strip(), self.recipient_ref.strip(), self.correlation_id.strip())):
            raise ValueError("Channel, recipient and correlation are required.")


@dataclass(frozen=True, slots=True)
class MultimodalIngestionRequest:
    tenant_id: str
    modality: ArtifactModality
    mime_type: str
    size_bytes: int
    channel: ChannelContext
    mission_id: str | None = None
    trace_id: str | None = None
    idempotency_key: str = ""
    duration_ms: int | None = None

    def __post_init__(self) -> None:
        if not self.tenant_id.strip() or not self.mime_type.strip():
            raise ValueError("Tenant and MIME are required.")
        if self.size_bytes <= 0 or (self.duration_ms is not None and self.duration_ms < 0):
            raise ValueError("Invalid ingestion size or duration.")
        if not self.idempotency_key.strip():
            raise ValueError("An idempotency key is required.")


@dataclass(frozen=True, slots=True)
class ProcessingDecision:
    mode: ProcessingMode
    reason: str
    max_cost_units: int

    def __post_init__(self) -> None:
        if not self.reason.strip() or self.max_cost_units < 0:
            raise ValueError("Invalid processing decision.")


class IngestionPolicyPort(Protocol):
    def decide(self, request: MultimodalIngestionRequest, identity: AuthenticatedIdentity) -> ProcessingDecision: ...


class StaticIngestionPolicy:
    """Explicit configuration only; actual tenant policy and budgets are external."""
    def __init__(self, *, allowed_mime: dict[ArtifactModality, frozenset[str]],
                 max_size_bytes: int, sync_max_bytes: int, max_cost_units: int) -> None:
        if max_size_bytes <= 0 or sync_max_bytes <= 0 or max_cost_units < 0:
            raise ValueError("Invalid policy configuration.")
        self.allowed_mime = allowed_mime
        self.max_size_bytes = max_size_bytes
        self.sync_max_bytes = sync_max_bytes
        self.max_cost_units = max_cost_units

    def decide(self, request: MultimodalIngestionRequest, identity: AuthenticatedIdentity) -> ProcessingDecision:
        if request.tenant_id != identity.tenant_id:
            raise PermissionError("Authenticated tenant mismatch.")
        if request.mime_type.lower().split(";", 1)[0].strip() not in self.allowed_mime.get(request.modality, frozenset()):
            raise ValueError("MIME type not permitted for modality.")
        if request.size_bytes > self.max_size_bytes:
            raise ValueError("Ingestion size quota exceeded.")
        mode = ProcessingMode.SYNC if (
            request.size_bytes <= self.sync_max_bytes
            and request.modality in (ArtifactModality.TEXT, ArtifactModality.IMAGE, ArtifactModality.AUDIO)
            and (request.duration_ms is None or request.duration_ms <= 30_000)
        ) else ProcessingMode.ASYNC
        return ProcessingDecision(mode=mode, reason="static_ingestion_policy", max_cost_units=self.max_cost_units)


class MultimodalGateway:
    """Validate canonical identity and delegate routing choice to an injected policy."""
    def __init__(self, policy: IngestionPolicyPort) -> None:
        self.policy = policy

    def accept(self, *, request: MultimodalIngestionRequest, identity: AuthenticatedIdentity) -> ProcessingDecision:
        if request.tenant_id != identity.tenant_id:
            raise PermissionError("Authenticated tenant mismatch.")
        return self.policy.decide(request, identity)
