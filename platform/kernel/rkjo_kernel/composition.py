"""Shipped API/worker composition. Network providers require explicit selection."""
import os
from dataclasses import replace
from urllib.parse import urlparse

import psycopg

from rkjo_kernel.kernel import RKJOKernel
from rkjo_kernel.memory.postgres import PostgresMemoryStore
from rkjo_kernel.llm.gateway import LLMGateway
from rkjo_kernel.llm.registry import LLMProviderRegistry
from rkjo_kernel.llm.router import LLMRouter
from rkjo_kernel.llm.ledger import PostgresLLMLedger


def _positive(name, default):
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f'{name} must be positive.')
    return value


class ConfiguredLLMGateway:
    """Server limits intersect context limits; callers cannot widen them."""
    def __init__(self, gateway, *, provider, local_only, total, output, input_limit):
        self.gateway = gateway
        self.provider = provider
        self.local_only = local_only
        self.total = total
        self.output = output
        self.input_limit = input_limit

    def check_retrieval_policy(self, context):
        from rkjo_kernel.llm.policy_resolver import LLMPolicyResolver
        if context is None or not context.tenant_id:
            raise ValueError('Canonical execution context required before retrieval.')
        policy = LLMPolicyResolver().resolve(context)
        if (self.local_only or policy.require_local_model or not policy.allow_external_processing):
            if os.getenv('RKJO_EMBEDDING_PROVIDER', 'deterministic') != 'deterministic':
                raise PermissionError('Execution policy forbids remote embeddings before retrieval.')

    def generate(self, request, *, context):
        if not context.tenant_id:
            raise ValueError('Tenant required for governed generation.')
        policy = dict(context.policy_context.get('llm') or {})
        allowed = policy.get('allowed_providers')
        if allowed and self.provider not in allowed:
            raise PermissionError('Configured provider is not allowed by the execution.')
        policy['allowed_providers'] = [self.provider]
        policy['fallback_chain'] = []  # one reserved call, never a hidden second provider
        if self.local_only:
            policy.update(require_local_model=True, allow_external_processing=False)
        limits = dict(context.budget.get('llm') or {})
        for key, server in [('max_total_tokens', self.total), ('max_output_tokens', self.output),
                            ('max_input_tokens', self.input_limit)]:
            supplied = limits.get(key)
            if supplied is not None and (type(supplied) is not int or supplied < 0):
                raise ValueError(f'{key} must be a non-negative integer.')
            limits[key] = min(supplied, server) if supplied is not None else server
        governed = replace(context, policy_context={**context.policy_context, 'llm': policy},
                           budget={**context.budget, 'llm': limits})
        return self.gateway.generate(request, context=governed)


def build_platform_kernel(*, agent_registry=None):
    database_url = (os.getenv('RKJO_DATABASE_URL') or os.getenv('DATABASE_URL') or '').strip()
    if not database_url:
        raise RuntimeError('An explicit database URL is required for durable kernel composition.')
    connect = lambda: psycopg.connect(database_url)
    memory = PostgresMemoryStore(connection_factory=connect, ensure_schema=True)
    provider = os.getenv('RKJO_LLM_PROVIDER', '').strip().lower()
    resources = ()
    gateway = None
    if provider:
        # Parse all settings before opening a client.
        total = _positive('RKJO_LLM_MAX_TOTAL_TOKENS', 65536)
        output = _positive('RKJO_LLM_MAX_OUTPUT_TOKENS', 512)
        input_limit = _positive('RKJO_LLM_MAX_INPUT_TOKENS', 32768)
        mode = os.getenv('RKJO_LLM_LOCAL_ONLY', 'true').lower()
        if mode not in {'true', 'false'}:
            raise ValueError('RKJO_LLM_LOCAL_ONLY must be true or false.')
        model = os.environ['RKJO_LLM_MODEL']
        timeout = _positive('RKJO_LLM_TIMEOUT_SECONDS', 60)
        ledger = PostgresLLMLedger(connect)
        if provider == 'ollama':
            from rkjo_kernel.llm.ollama_adapter import OllamaLLMAdapter
            url = os.getenv('RKJO_OLLAMA_BASE_URL', 'http://127.0.0.1:11434')
            parsed = urlparse(url)
            # An arbitrary Ollama URL must never masquerade as a local model.
            if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} or parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or parsed.fragment:
                raise ValueError('Local Ollama requires an explicit loopback HTTP endpoint.')
            adapter = OllamaLLMAdapter(base_url=url, default_model=model, timeout_seconds=timeout, think=False, require_usage=True)
        elif provider == 'openai':
            from rkjo_kernel.llm.openai_adapter import OpenAILLMAdapter
            adapter = OpenAILLMAdapter(api_key=os.environ['OPENAI_API_KEY'], default_model=model,
                                       timeout_seconds=timeout, max_retries=0, require_usage=True)
        else:
            raise ValueError('RKJO_LLM_PROVIDER must be ollama or openai.')
        registry = LLMProviderRegistry()
        registry.register(provider, adapter, is_local=provider == 'ollama')
        raw_gateway = LLMGateway(router=LLMRouter(registry=registry, default_provider=provider), ledger=ledger)
        gateway = ConfiguredLLMGateway(raw_gateway, provider=provider, local_only=mode == 'true',
                                       total=total, output=output, input_limit=input_limit)
        resources = (adapter,)
    return RKJOKernel(agent_registry=agent_registry, memory_store=memory,
                      llm_gateway=gateway, owned_resources=resources)


def build_answering_service(kernel, *, search_service=None, observer=None):
    from rkjo_kernel.rag.rag_answering import RAGAnsweringService
    from rkjo_kernel.rag.llm_generation import LLMBackedAnswerGenerator
    from rkjo_kernel.rag.context_builder import CitationContextBuilder
    from rkjo_kernel.rag.service_factory import build_search_service
    if kernel.llm_gateway is None:
        raise RuntimeError('Explicit RKJO_LLM_PROVIDER and RKJO_LLM_MODEL are required for answering.')
    if kernel.llm_gateway.local_only and os.getenv('RKJO_EMBEDDING_PROVIDER', 'deterministic') != 'deterministic':
        raise PermissionError('Local-only answering requires local embeddings before retrieval.')
    return RAGAnsweringService(
        observer=observer,
        preflight=kernel.llm_gateway.check_retrieval_policy,        search_service=search_service or build_search_service(),
        generator=LLMBackedAnswerGenerator(gateway=kernel.llm_gateway, context_runtime=kernel.context_runtime),
        context_builder=CitationContextBuilder(max_characters=_positive('RKJO_RAG_MAX_CONTEXT_CHARACTERS', 12000)),
    )
