import pytest

from rkjo_kernel.artifacts.models import ArtifactModality
from rkjo_kernel.multimodal.gateway import (
    AuthenticatedIdentity, ChannelContext, MultimodalGateway,
    MultimodalIngestionRequest, ProcessingMode, StaticIngestionPolicy,
)


def setup():
    policy = StaticIngestionPolicy(
        allowed_mime={
            ArtifactModality.TEXT: frozenset({"text/plain"}),
            ArtifactModality.AUDIO: frozenset({"audio/ogg"}),
            ArtifactModality.VIDEO: frozenset({"video/mp4"}),
        },
        max_size_bytes=10_000_000, sync_max_bytes=100_000, max_cost_units=100,
    )
    return MultimodalGateway(policy)


def req(modality=ArtifactModality.AUDIO, mime="audio/ogg", size=4000, duration=1000, tenant="a"):
    return MultimodalIngestionRequest(
        tenant_id=tenant, modality=modality, mime_type=mime, size_bytes=size,
        duration_ms=duration, idempotency_key="request-1",
        channel=ChannelContext(channel="whatsapp", recipient_ref="user-opaque", correlation_id="corr-1"),
    )


def test_short_whatsapp_audio_uses_sync():
    assert setup().accept(request=req(), identity=AuthenticatedIdentity("a", "user")).mode == ProcessingMode.SYNC


def test_long_video_uses_async():
    assert setup().accept(request=req(ArtifactModality.VIDEO, "video/mp4", 2_000_000, 90_000), identity=AuthenticatedIdentity("a", "user")).mode == ProcessingMode.ASYNC


def test_tenant_spoofing_rejected():
    with pytest.raises(PermissionError, match="tenant"):
        setup().accept(request=req(tenant="other"), identity=AuthenticatedIdentity("a", "user"))


def test_wrong_mime_rejected():
    with pytest.raises(ValueError, match="MIME"):
        setup().accept(request=req(mime="video/mp4"), identity=AuthenticatedIdentity("a", "user"))


def test_size_quota_rejected():
    with pytest.raises(ValueError, match="quota"):
        setup().accept(request=req(size=11_000_000), identity=AuthenticatedIdentity("a", "user"))


def test_required_request_fields():
    with pytest.raises(ValueError, match="idempotency"):
        MultimodalIngestionRequest(tenant_id="a", modality=ArtifactModality.TEXT, mime_type="text/plain",
            size_bytes=20, channel=ChannelContext("api", "u", "c"))
