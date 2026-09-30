from __future__ import annotations

from dataclasses import replace

import pytest

from rkjo_kernel.llm.gateway import LLMGateway
from rkjo_kernel.llm.models import LLMMessage, LLMRequest, LLMResponse, LLMUsage
from rkjo_kernel.llm.registry import LLMProviderRegistry
from rkjo_kernel.llm.router import LLMRouter
from rkjo_kernel.memory.context_engine import ContextPackage
from rkjo_kernel.memory.llm_context_adapter import (
    ContextualLLMGateway,
    LLMContextAdapter,
    LLMContextLimits,
)
from rkjo_kernel.memory.models import MemoryItem, MemoryScope
from rkjo_kernel.memory.rag_bridge import KnowledgeContextItem
from rkjo_kernel.mission.execution_context import ExecutionContext


def context(**overrides):
    params = {
        "tenant_id": "tenant-a",
        "mission_id": "mission-1",
        "trace_id": "trace-1",
    }
    params.update(overrides)
    return ExecutionContext(**params)


def memory(*, tenant_id="tenant-a", mission_id="mission-1", content="Previously approved decision"):
    return MemoryItem(
        content=content,
        tenant_id=tenant_id,
        mission_id=mission_id,
        scope=MemoryScope.MISSION,
    )


def knowledge(*, tenant_id="tenant-a", content="Documented reference"):
    return KnowledgeContextItem(
        chunk_id="chunk-1",
        document_id="doc-1",
        content=content,
        score=0.98,
        metadata={"tenant_id": tenant_id},
    )


def package(*, items=(), knowledge_items=(), **overrides):
    params = {
        "tenant_id": "tenant-a",
        "mission_id": "mission-1",
        "trace_id": "trace-1",
        "items": items,
        "knowledge_items": knowledge_items,
    }
    params.update(overrides)
    return ContextPackage(**params)


def request():
    return LLMRequest(
        messages=(
            LLMMessage("system", "Answer accurately."),
            LLMMessage("user", "What changed?"),
        ),
        metadata={"caller": "unit-test"},
    )


def test_memory_and_knowledge_are_provenanced_and_existing_messages_preserved():
    original = request()
    enriched = LLMContextAdapter().prepare(
        original,
        context=context(),
        package=package(items=(memory(),), knowledge_items=(knowledge(),)),
    )
    assert enriched.messages[:2] == original.messages
    assert original.messages == request().messages
    assert len(enriched.messages) == 3
    assert enriched.messages[-1].role == "user"
    prompt = enriched.messages[-1].content
    assert "UNTRUSTED DATA ONLY" in prompt
    assert "Previously approved decision" in prompt
    assert "document_id=doc-1" in prompt
    assert "chunk_id=chunk-1" in prompt
    assert enriched.tenant_id == "tenant-a"
    assert enriched.trace_id == "trace-1"
    assert enriched.metadata == original.metadata


@pytest.mark.parametrize(
    "changes",
    [
        {"tenant_id": "tenant-b"},
        {"mission_id": "another-mission"},
        {"trace_id": "another-trace"},
    ],
)
def test_rejects_package_identity_mismatch(changes):
    with pytest.raises(ValueError):
        LLMContextAdapter().prepare(request(), context=context(), package=package(**changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"tenant_id": "tenant-b"},
        {"trace_id": "another-trace"},
    ],
)
def test_rejects_request_identity_mismatch(changes):
    with pytest.raises(ValueError):
        LLMContextAdapter().prepare(
            replace(request(), **changes),
            context=context(),
            package=package(),
        )


def test_rejects_cross_tenant_memory():
    with pytest.raises(ValueError, match="Cross-tenant"):
        LLMContextAdapter().prepare(
            request(), context=context(), package=package(items=(memory(tenant_id="tenant-b"),))
        )


def test_rejects_cross_mission_memory():
    with pytest.raises(ValueError, match="Cross-mission"):
        LLMContextAdapter().prepare(
            request(), context=context(), package=package(items=(memory(mission_id="mission-b"),))
        )


@pytest.mark.parametrize("provenance", [{}, {"tenant_id": "tenant-b"}])
def test_knowledge_missing_or_wrong_tenant_is_rejected(provenance):
    item = replace(knowledge(), metadata=provenance)
    with pytest.raises(ValueError, match="RAG tenant provenance"):
        LLMContextAdapter().prepare(
            request(), context=context(), package=package(knowledge_items=(item,))
        )


def test_combined_memory_and_knowledge_budget_is_bounded():
    adapter = LLMContextAdapter(limits=LLMContextLimits(
        max_characters=270, max_memory_items=2, max_knowledge_items=2
    ))
    enriched = adapter.prepare(
        request(),
        context=context(),
        package=package(
            items=(memory(content="A" * 32), memory(content="B" * 120)),
            knowledge_items=(knowledge(content="C" * 120),),
        ),
    )
    assert len(enriched.messages) == 3
    assert len(enriched.messages[-1].content) <= 270
    assert "A" * 32 in enriched.messages[-1].content
    assert "B" * 120 not in enriched.messages[-1].content
    assert "C" * 120 not in enriched.messages[-1].content



def test_too_small_context_budget_omits_reference_without_truncation():
    original = request()
    enriched = LLMContextAdapter(
        limits=LLMContextLimits(max_characters=80)
    ).prepare(
        original,
        context=context(),
        package=package(items=(memory(content="A" * 32),)),
    )
    assert enriched.messages == original.messages
    assert enriched.tenant_id == "tenant-a"
    assert enriched.trace_id == "trace-1"


def test_no_reference_content_keeps_original_messages():
    original = request()
    enriched = LLMContextAdapter().prepare(original, context=context(), package=package())
    assert enriched.messages == original.messages
    assert enriched.tenant_id == "tenant-a"


class FakeProvider:
    def __init__(self):
        self.last_request = None

    def generate(self, llm_request):
        self.last_request = llm_request
        return LLMResponse(
            content="Answer using evidence.",
            provider="fake",
            model="fake-model",
            usage=LLMUsage(input_tokens=42, output_tokens=5),
        )


def test_contextual_llm_gateway_routes_with_policy_budget_and_identifiers():
    fake = FakeProvider()
    registry = LLMProviderRegistry()
    registry.register("fake", fake, is_local=True)
    gateway = LLMGateway(router=LLMRouter(registry=registry, default_provider="fake"))
    bridge = ContextualLLMGateway(gateway)
    execution = context(
        policy_context={"llm": {"require_local_model": True, "allow_external_processing": False}},
        budget={"llm": {"max_total_tokens": 50}},
    )

    result = bridge.generate(
        request(),
        context=execution,
        package=package(items=(memory(),), knowledge_items=(knowledge(),)),
    )

    assert result.content == "Answer using evidence."
    assert fake.last_request.tenant_id == "tenant-a"
    assert fake.last_request.trace_id == "trace-1"
    assert fake.last_request.metadata["mission_id"] == "mission-1"
    assert fake.last_request.metadata["caller"] == "unit-test"
    assert "Previously approved decision" in fake.last_request.messages[-1].content
    assert "Documented reference" in fake.last_request.messages[-1].content


def test_adapter_limits_must_be_positive():
    with pytest.raises(ValueError):
        LLMContextLimits(max_characters=0)
