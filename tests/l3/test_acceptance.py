"""Real Ollama, PostgreSQL, RabbitMQ and shipped factories; never silently skipped."""
import hashlib
import json
import os
import re
from threading import Thread
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest

from tests.l1.test_acceptance import DB, EVIDENCE, wait
from tests.l2.test_authorization import secured
from rkjo_kernel.composition import build_platform_kernel, build_answering_service
from rkjo_kernel.memory.models import MemoryItem, MemoryScope
from rkjo_kernel.mission.execution_context import ExecutionContext
from rkjo_kernel.llm.models import LLMRequest, LLMMessage
from rkjo_kernel.llm.gateway import LLMBudgetExceededError
from rkjo_kernel.rag.models import Document
from rkjo_api.dependencies import get_rag_ingestion_pipeline

CORPUS = json.loads(Path(__file__).with_name('corpus.json').read_text())


@pytest.fixture
def recorded_provider(monkeypatch):
    upstream = os.environ['RKJO_OLLAMA_BASE_URL']
    calls = []
    class Forwarder(BaseHTTPRequestHandler):
        def do_POST(self):
            raw = self.rfile.read(int(self.headers['Content-Length']))
            headers = {key:value for key,value in self.headers.items() if key.lower().startswith('x-rkjo-')}
            calls.append({'payload':json.loads(raw),'headers':headers})
            response = httpx.post(upstream+self.path, content=raw,
                                  headers={**headers, 'Content-Type':'application/json'},timeout=90)
            self.send_response(response.status_code)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(response.content)
        def log_message(self,*_): pass
    server = ThreadingHTTPServer(('127.0.0.1',0),Forwarder)
    thread = Thread(target=server.serve_forever,daemon=True)
    thread.start()
    monkeypatch.setenv('RKJO_OLLAMA_BASE_URL',f'http://127.0.0.1:{server.server_port}')
    try: yield calls
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


@pytest.fixture
def real_stack(recorded_provider, secured):
    # Force proxy configuration before the shipped worker/API processes start.
    return secured, recorded_provider


def test_real_corpus_memory_worker_restart_and_http_factory(real_stack):
    s, provider_calls = real_stack
    # Dedicated test DB: avoid another run's corpus, never an application database.
    pipeline = get_rag_ingestion_pipeline()
    s.sql('TRUNCATE rag_chunks')
    for doc in CORPUS['documents']:
        pipeline.retriever.ingest(Document(document_id=doc['id'], content=doc['text'],
                                           metadata={'tenant_id':doc['tenant']}))
    metrics = []
    s.start('results')
    s.start('outbox')
    for case in CORPUS['cases']:
        identifier = 'l3-' + uuid4().hex
        payload = s.payload(identifier)
        payload['input_data'] = {'operation':'rag_answer', 'question':case['question']}
        payload['steps'] = payload['steps'][:1]
        assert s.request('POST','/workflows/executions',json=payload).status_code == 201
        meta = s.stored(identifier)['metadata']
        kernel = build_platform_kernel()
        try:
            a = MemoryItem(memory_id='a-'+identifier, content='Référence neutre de la mission Atlas.',
                           tenant_id='tenant-a', scope=MemoryScope.MISSION, mission_id=meta['mission_id'])
            b = MemoryItem(memory_id='b-'+identifier, content='INTERDIT_B', tenant_id='tenant-b',
                           scope=MemoryScope.MISSION, mission_id=meta['mission_id'])
            kernel.memory_store.write(a)
            kernel.memory_store.write(b)
            kernel.memory_store.write(MemoryItem(content='X'*6000, tenant_id='tenant-a',
                                      scope=MemoryScope.MISSION, mission_id=meta['mission_id']))
        finally:
            kernel.stop()
        s.stop('worker')
        s.start('worker')
        s.start_execution(identifier)
        wait(lambda: s.stored(identifier)['status'] in {'completed','failed'}, timeout=90)
        stored = s.stored(identifier)
        assert stored['status'] == 'completed', stored
        result = stored['context']['outputs']['first']
        assert result['context'] == {k:meta[k] for k in ('tenant_id','mission_id','trace_id')} | {'memory_ids':[a.memory_id]}
        answer = result['answer']
        assert case['required'].casefold() in answer.casefold(), result
        assert not any(word in answer for word in case['forbidden'])
        receipts = s.sql('SELECT tenant_id,mission_id,trace_id,state,receipt FROM rkjo_llm_calls WHERE mission_id=%s', (meta['mission_id'],))
        if case['document']:
            source_ids = [source['document_id'] for source in result['sources']]
            rank = source_ids.index(case['document']) + 1
            assert '[1]' in answer and source_ids[0] == case['document']
            assert len(receipts) == 1 and receipts[0][:4] == ('tenant-a',meta['mission_id'],meta['trace_id'],'succeeded')
            receipt = receipts[0][4]
            assert receipt['memory_ids'] == [a.memory_id]
            assert receipt['provider'] == 'ollama' and receipt['model'] == os.environ['RKJO_LLM_MODEL']
            assert receipt['input_tokens'] > 0 and 0 < receipt['output_tokens'] <= 256
            call = next(c for c in provider_calls if c['headers'].get('X-RKJO-mission-id') == meta['mission_id'])
            assert call['headers']['X-RKJO-tenant-id'] == meta['tenant_id']
            assert call['headers']['X-RKJO-trace-id'] == meta['trace_id']
            messages = tuple(LLMMessage(**m) for m in call['payload']['messages'])
            assert hashlib.sha256(repr(messages).encode()).hexdigest() == receipt['request_sha256']
            reference = messages[-1].content
            assert a.memory_id in reference and 'INTERDIT_B' not in repr(messages) and 'X'*6000 not in reference
            assert len(reference) <= 6000
            citations = {int(x) for x in re.findall(r'\[(\d+)\]',answer)}
            assert citations and citations <= {source['citation'] for source in result['sources']}
            metrics.append({'hit':1, 'rr':1/rank, 'faithful':1, 'receipt':receipt,
                            'answer':answer, 'source_ids':source_ids, 'citation_errors':0})
        else:
            assert result['sources'] == [] and receipts == []
            metrics.append({'no_answer':1, 'answer':answer, 'source_ids':[], 'citation_errors':0})
    measured = {'hit_at_3':sum(m['hit'] for m in metrics[:2])/2,
                'mrr':sum(m['rr'] for m in metrics[:2])/2,
                'faithfulness':sum(m['faithful'] for m in metrics[:2])/2,
                'no_answer':metrics[2]['no_answer']}
    assert all(measured[k] >= value for k,value in CORPUS['thresholds'].items())
    # A real HTTP API call also uses the shipped answering dependency, no override.
    response = httpx.post(s.url+'/rag/answer', headers=s.headers['a'],
                         json={'question':CORPUS['cases'][0]['question']}, timeout=90)
    assert response.status_code == 200, response.text
    assert 'AZUR' in response.json()['answer'] and '[1]' in response.json()['answer']
    assert s.request('POST','/rag/answer','b',json={'question':CORPUS['cases'][0]['question'],
                      'filters':{'tenant_id':'tenant-a'}}).status_code == 403
    (EVIDENCE/'corpus-result.json').write_text(json.dumps({'measured':measured, 'thresholds':CORPUS['thresholds'],
                                                        'cases':metrics},indent=2))


def test_real_budget_exhaustion_survives_new_factory():
    context = ExecutionContext(mission_id='l3-budget-'+uuid4().hex,tenant_id='tenant-a',
                               budget={'llm':{'max_total_tokens':600, 'max_output_tokens':256}})
    request = LLMRequest(messages=(LLMMessage(role='user',content='Réponds seulement OK.'),))
    # Reserve the entire mission envelope, so any actual usage prevents repetition.
    input_units = sum(len(m.content.encode())+256 for m in request.messages)
    context.budget['llm']['max_total_tokens'] = input_units + 256
    kernel = build_platform_kernel()
    try:
        answer = kernel.llm_gateway.generate(request,context=context)
        assert answer.usage.total_tokens > 0
    finally:
        kernel.stop()
    kernel = build_platform_kernel()
    try:
        with pytest.raises(LLMBudgetExceededError, match='before call'):
            kernel.llm_gateway.generate(request,context=context)
        with psycopg.connect(DB) as con:
            assert con.execute('SELECT count(*) FROM rkjo_llm_calls WHERE mission_id=%s',(context.mission_id,)).fetchone()[0] == 1
    finally:
        kernel.stop()
