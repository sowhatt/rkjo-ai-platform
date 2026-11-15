"""L3 failure contracts: real HTTP clients and SQL, controlled local provider replies."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from threading import Thread
import time
from uuid import uuid4

import psycopg
import pytest

from rkjo_kernel.composition import build_platform_kernel, build_answering_service
from rkjo_kernel.kernel import RKJOKernel
from rkjo_kernel.llm.gateway import LLMBudgetExceededError
from rkjo_kernel.llm.ledger import PostgresLLMLedger
from rkjo_kernel.llm.models import LLMMessage, LLMRequest
from rkjo_kernel.llm.router import LLMRoutingError
from rkjo_kernel.mission.execution_context import ExecutionContext


@contextmanager
def provider_server(mode='success'):
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            calls.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            if mode == 'timeout':
                time.sleep(1.3)
            self.send_response(500 if mode == 'error' else 200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            body = {'model':'contract-model','message':{'content':'OK'}, 'prompt_eval_count':12, 'eval_count':2}
            if mode == 'excess': body['eval_count'] = 1000
            if mode == 'missing_usage': body.pop('eval_count')
            try: self.wfile.write(json.dumps(body).encode())
            except BrokenPipeError: pass
        def log_message(self, *_): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try: yield f'http://127.0.0.1:{server.server_port}', calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv('RKJO_LLM_PROVIDER','ollama')
    monkeypatch.setenv('RKJO_LLM_MODEL','contract-model')
    monkeypatch.setenv('RKJO_LLM_LOCAL_ONLY','true')
    monkeypatch.setenv('RKJO_LLM_TIMEOUT_SECONDS','1')
    monkeypatch.setenv('RKJO_LLM_MAX_OUTPUT_TOKENS','32')
    monkeypatch.setenv('RKJO_LLM_MAX_TOTAL_TOKENS','4096')
    monkeypatch.setenv('RKJO_LLM_MAX_INPUT_TOKENS','2048')
    return monkeypatch


def context():
    return ExecutionContext(mission_id='l3-contract-'+uuid4().hex,tenant_id='tenant-a')


def request():
    return LLMRequest(messages=(LLMMessage(role='user',content='Neutral contract prompt.'),))


def receipts(ctx):
    with psycopg.connect(os.environ['RKJO_TEST_DATABASE_URL']) as con:
        return con.execute('SELECT state,receipt FROM rkjo_llm_calls WHERE mission_id=%s',(ctx.mission_id,)).fetchall()


def test_local_only_blocks_real_remote_client_before_http(configured):
    with provider_server() as (url,calls):
        configured.setenv('RKJO_LLM_PROVIDER','openai')
        configured.setenv('OPENAI_API_KEY','l3-contract-placeholder')
        configured.setenv('OPENAI_BASE_URL',url)
        kernel = build_platform_kernel()
        try:
            with pytest.raises(LLMRoutingError): kernel.llm_gateway.generate(request(),context=context())
            assert calls == []
        finally: kernel.stop()


@pytest.mark.parametrize('mode', ['error','timeout','missing_usage'])
def test_provider_error_is_not_success_and_keeps_reservation(configured, mode):
    with provider_server(mode) as (url,calls):
        configured.setenv('RKJO_OLLAMA_BASE_URL',url)
        ctx = context()
        kernel = build_platform_kernel()
        try:
            with pytest.raises(LLMRoutingError): kernel.llm_gateway.generate(request(),context=ctx)
            assert len(calls) == 1
            assert receipts(ctx)[0][0] == 'uncertain'
        finally: kernel.stop()


def test_provider_output_limit_and_canonical_receipt(configured):
    with provider_server() as (url,calls):
        configured.setenv('RKJO_OLLAMA_BASE_URL',url)
        ctx = context()
        kernel = build_platform_kernel()
        try:
            answer = kernel.llm_gateway.generate(request(),context=ctx)
            assert answer.content == 'OK' and answer.usage.total_tokens == 14
            assert calls[0]['options']['num_predict'] == 32 and calls[0]['think'] is False
            assert receipts(ctx)[0][0] == 'succeeded'
            with pytest.raises(ValueError,match='conflicts'):
                kernel.llm_gateway.generate(replace(request(),tenant_id='tenant-b'),context=ctx)
            assert len(calls) == 1
        finally: kernel.stop()


def test_over_usage_is_rejected_and_recorded(configured):
    with provider_server('excess') as (url,calls):
        configured.setenv('RKJO_OLLAMA_BASE_URL',url)
        kernel = build_platform_kernel()
        ctx = context()
        try:
            with pytest.raises(LLMBudgetExceededError): kernel.llm_gateway.generate(request(),context=ctx)
            state, receipt = receipts(ctx)[0]
            assert state == 'rejected' and receipt['output_tokens'] == 1000
            assert len(calls) == 1
        finally: kernel.stop()


@pytest.mark.parametrize('budget', [{'max_total_tokens':0},{'max_output_tokens':0},{'max_cost':1}])
def test_exhausted_or_unpriced_budget_refused_before_http(configured,budget):
    with provider_server() as (url,calls):
        configured.setenv('RKJO_OLLAMA_BASE_URL',url)
        kernel = build_platform_kernel()
        try:
            with pytest.raises(LLMBudgetExceededError):
                kernel.llm_gateway.generate(request(),context=replace(context(),budget={'llm':budget}))
            assert calls == []
        finally: kernel.stop()


def test_sql_reservation_is_atomic_and_crash_remains_charged():
    connect = lambda: psycopg.connect(os.environ['RKJO_TEST_DATABASE_URL'])
    ledger = PostgresLLMLedger(connect)
    ctx = context()
    def reserve(_):
        try: return ledger.reserve(ctx,100,100,{})
        except LLMBudgetExceededError: return None
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(reserve,range(2)))
    assert sum(value is not None for value in results) == 1
    fresh = PostgresLLMLedger(connect)
    with pytest.raises(LLMBudgetExceededError): fresh.reserve(ctx,1,100,{})
    assert receipts(ctx)[0][0] == 'reserved'


def test_kernel_closes_owned_client_once_and_rejects_restart():
    class Resource:
        count = 0
        def close(self): self.count += 1
    resource = Resource()
    kernel = RKJOKernel(owned_resources=(resource,))
    kernel.start(); kernel.start(); kernel.stop(); kernel.stop()
    assert resource.count == 1 and kernel.health()['status'] == 'stopped'
    with pytest.raises(Exception,match='Closed kernel'): kernel.start()


def test_remote_ollama_cannot_claim_locality(configured):
    configured.setenv('RKJO_OLLAMA_BASE_URL','https://example.invalid')
    with pytest.raises(ValueError,match='loopback'): build_platform_kernel()


def test_local_only_answering_blocks_remote_embedding(configured):
    configured.setenv('RKJO_EMBEDDING_PROVIDER','openai')
    configured.setenv('RKJO_OLLAMA_BASE_URL','http://127.0.0.1:11434')
    kernel = build_platform_kernel()
    try:
        with pytest.raises(PermissionError,match='local embeddings'): build_answering_service(kernel)
    finally: kernel.stop()


def test_execution_policy_cannot_be_weakened_by_server_embedding_setting(configured):
    configured.setenv('RKJO_LLM_LOCAL_ONLY','false')
    configured.setenv('RKJO_EMBEDDING_PROVIDER','openai')
    kernel = build_platform_kernel()
    class SearchSpy:
        calls = 0
        def search(self,*args,**kwargs):
            self.calls += 1
            raise AssertionError('Remote embedding path must not be entered.')
    search = SearchSpy()
    try:
        service = build_answering_service(kernel,search_service=search)
        ctx = replace(context(),policy_context={'llm':{'require_local_model':True}})
        with pytest.raises(PermissionError,match='before retrieval'):
            service.answer('neutral',execution_context=ctx)
        assert search.calls == 0
    finally: kernel.stop()
