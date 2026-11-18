"""L2 acceptance: shipped HTTP/worker processes and dedicated real SQL/AMQP."""
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import httpx
import jwt
import time
import pika
import psycopg
import pytest

from rkjo_api.jwt_auth import create_access_token
from rkjo_api.security import ApiRole
from rkjo_kernel.security.authority import (
    PostgreSQLSecurityAuthority, AuthorityUnavailable, AuthorityDenied, user_claim, api_claim,
)
from rkjo_kernel.security.migrations import apply_authority_migrations
from rkjo_kernel.messages.agent_message import AgentMessage
from tests.l1.test_acceptance import Stack, DB, MQ, ROOT, wait


@pytest.fixture
def secured(request):
    authority = PostgreSQLSecurityAuthority(DB)
    with psycopg.connect(DB) as conn:
        apply_authority_migrations(conn)
        conn.execute('TRUNCATE security_grants, security_authority_audit')
    # Separate project/database; only queues belonging to this recipe are purged.
    with pika.BlockingConnection(pika.URLParameters(MQ)) as conn:
        channel = conn.channel()
        for name in ('rkjo.platform.worker', 'rkjo.workflow.results'):
            for queue in (name, name + '.dlq'):
                channel.queue_declare(queue, durable=True)
                channel.queue_purge(queue)
    value = Stack(request.node.name)
    value.authority = authority
    for key, tenant, subject, role in [('a','tenant-a','alice','operator'),
            ('b','tenant-b','bob','operator'), ('admin','tenant-a','admin-a','admin'),
            ('adminb','tenant-b','admin-b','admin')]:
        for claim in (user_claim(tenant,subject), api_claim(tenant,subject,role)):
            authority.change(claim, enabled=True, expected_version=0, actor='recipe-provisioner')
        value.headers[key] = {'Authorization': 'Bearer ' + create_access_token(
            subject=subject, role=ApiRole(role), tenant_id=tenant)}
    value.headers['unknown'] = {'Authorization': 'Bearer ' + create_access_token(
        subject='alice', role=ApiRole.OPERATOR, tenant_id='tenant-unknown')}
    value.headers['expired'] = {'Authorization': 'Bearer ' + jwt.encode(
        {'sub':'alice','role':'operator','tenant_id':'tenant-a','iat':int(time.time())-100,
         'exp':int(time.time())-10}, os.environ['RKJO_JWT_SECRET'], algorithm='HS256')}
    try:
        value.start('api')
        value.start('worker')
        yield value
    finally:
        value.close()
        with psycopg.connect(DB) as conn:
            audit = conn.execute('SELECT tenant_id,kind,version,decision FROM security_authority_audit ORDER BY audit_id').fetchall()
        (value.dir/'authority-audit.json').write_text(json.dumps(audit))


def mutation(stack, method, path, identity, metadata=None):
    kwargs = {}
    if method != 'DELETE':
        kwargs = {'files': {'file': ('neutral.txt', f'Neutral technical document {identity} {uuid4().hex}.'.encode(), 'text/plain')},
                  'data': {'metadata': json.dumps(metadata or {})}}
    return stack.request(method, path, identity, **kwargs)


def test_document_mutations_two_tenants_and_no_legacy_fallback(secured):
    s = secured
    a = mutation(s, 'POST', '/rag/documents', 'admin')
    b = mutation(s, 'POST', '/rag/documents', 'adminb')
    assert a.status_code == b.status_code == 201
    doc = a.json()['document_id']
    before = s.sql('SELECT * FROM rag_chunks ORDER BY chunk_id')
    for identity, code in [('unbound',403),('unknown',403),('expired',401),('anonymous',401)]:
        for method, path in [('POST','/rag/documents'),('PUT',f'/rag/documents/{doc}'),('DELETE',f'/rag/documents/{doc}')]:
            assert mutation(s,method,path,identity,{'tenant_id':'tenant-a'}).status_code == code
    for method,path in [('POST','/rag/documents'),('PUT',f'/rag/documents/{doc}')]:
        assert mutation(s,method,path,'admin',{'tenant_id':'tenant-b'}).status_code == 403
    assert mutation(s,'DELETE',f'/rag/documents/{doc}','adminb').status_code == 404
    assert mutation(s,'PUT',f'/rag/documents/{doc}','adminb').status_code == 404
    assert s.sql('SELECT * FROM rag_chunks ORDER BY chunk_id') == before
    assert mutation(s,'PUT',f'/rag/documents/{doc}','admin').status_code == 200
    assert mutation(s,'DELETE',f'/rag/documents/{doc}','admin').status_code == 200
    assert s.sql("SELECT count(*) FROM rag_chunks WHERE metadata->>'tenant_id'='tenant-b'")[0][0] > 0


def test_queued_work_revoked_before_worker_admission(secured):
    s = secured
    identifier = s.create()
    s.start_execution(identifier)
    request = AgentMessage.model_validate(s.intents(identifier)[0][0])
    # Stop only the consumer while its registration/lease is no longer needed.
    s.stop('worker', kill=True)
    s.publish('rkjo.platform.worker', request)
    claim = user_claim('tenant-a','alice')
    s.authority.change(claim, enabled=False, expected_version=1, actor='recipe-revoker')
    s.start('worker')
    wait(lambda: s.take('rkjo.platform.worker.dlq'))
    assert not s.stored(identifier)['context']['outputs']
    assert len(s.intents(identifier)) == 1
    assert s.take('rkjo.workflow.results') is None
    assert s.request('GET',f'/workflows/executions/{identifier}').status_code == 403
    assert s.sql("SELECT count(*) FROM security_authority_audit WHERE decision='deny' AND version=2")[0][0] >= 1
    # Trusted explicit CAS regrant, then original message remains usable.
    s.authority.change(claim, enabled=True, expected_version=2, actor='recipe-regrant')
    s.start('results'); s.start('outbox')
    s.complete(identifier)


def test_authority_unavailable_refuses_http_and_worker_without_effect(secured):
    s = secured
    identifier = s.create(); s.start_execution(identifier)
    request = AgentMessage.model_validate(s.intents(identifier)[0][0])
    s.sql('ALTER TABLE security_grants RENAME TO l2_unavailable_grants')
    try:
        assert s.request('GET',f'/workflows/executions/{identifier}').status_code == 503
        s.publish('rkjo.platform.worker', request)
        wait(lambda: s.take('rkjo.platform.worker.dlq'))
        assert not s.stored(identifier)['context']['outputs']
        assert s.take('rkjo.workflow.results') is None
    finally:
        s.sql('ALTER TABLE l2_unavailable_grants RENAME TO security_grants')
    s.start('results'); s.start('outbox'); s.complete(identifier)


def test_concurrent_grants_cas_and_durable_audit_across_processes(secured):
    s = secured
    script = ROOT/'tests/l2/change_grant.py'
    barrier = s.dir/'release-changes'
    children = [subprocess.Popen([sys.executable,str(script),str(barrier)],env=s.env,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
    barrier.touch()
    answers = [p.communicate(timeout=15) for p in children]
    assert sorted(out.strip() for out,err in answers) == ['changed','conflict']
    assert all(p.returncode == 0 for p in children)
    fresh = PostgreSQLSecurityAuthority(DB)
    with pytest.raises(AuthorityDenied): fresh.check(api_claim('tenant-a','alice','operator'))
    with psycopg.connect(DB) as conn:
        assert apply_authority_migrations(conn) == ()
        rows = conn.execute("SELECT version,decision FROM security_authority_audit WHERE kind='api' AND tenant_id='tenant-a' AND decision='revoke'").fetchall()
        assert rows == [(2,'revoke')]
    assert s.request('POST','/workflows/executions',json=s.payload('denied-'+uuid4().hex)).status_code == 403


def test_audit_failure_refuses_before_operation(secured):
    s = secured
    identifier = 'not-created-'+uuid4().hex
    s.sql('ALTER TABLE security_authority_audit RENAME TO l2_unavailable_audit')
    try:
        assert s.request('POST','/workflows/executions',json=s.payload(identifier)).status_code == 503
        assert not s.sql('SELECT 1 FROM workflow_executions WHERE execution_id=%s',(identifier,))
        with pytest.raises(AuthorityUnavailable):
            s.authority.change(user_claim('tenant-new','no-grant'),enabled=True,expected_version=0,actor='test')
        assert not s.sql("SELECT 1 FROM security_grants WHERE tenant_id='tenant-new'")
    finally:
        s.sql('ALTER TABLE l2_unavailable_audit RENAME TO security_authority_audit')


def test_revocation_waits_for_admitted_operation_and_migration_integrity(secured):
    s = secured
    barrier = s.dir/'release-changes'; barrier.touch()
    with s.authority.operation():
        child = subprocess.Popen([sys.executable,str(ROOT/'tests/l2/change_grant.py'),str(barrier)],
            env=s.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            wait(lambda: s.sql("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND NOT granted")[0][0] == 1)
            assert child.poll() is None
        except BaseException:
            child.kill(); child.wait(); raise
    out, err = child.communicate(timeout=10)
    assert child.returncode == 0 and out.strip() == 'changed'
    assert s.request('POST','/workflows/executions',json=s.payload('revoked-'+uuid4().hex)).status_code == 403
    with psycopg.connect(DB) as conn:
        original = conn.execute('SELECT sha256 FROM security_schema_migrations').fetchone()[0]
        conn.execute("UPDATE security_schema_migrations SET sha256='modified'")
    try:
        with psycopg.connect(DB) as conn, pytest.raises(ValueError,match='changed security migration'):
            apply_authority_migrations(conn)
    finally:
        s.sql('UPDATE security_schema_migrations SET sha256=%s',(original,))


def test_real_oidc_tenant_mapping_and_foreign_expired_forged_tokens(secured):
    from hashlib import sha256
    from rkjo_api.oidc_auth import resolve_oidc_identity_with_tenant
    s = secured
    issuer = os.environ['RKJO_OIDC_ISSUER']
    def token(client):
        response = httpx.post(issuer+'/protocol/openid-connect/token',data={
            'grant_type':'client_credentials','client_id':'l2-'+client,
            'client_secret':'l2-only-synthetic-client-secret',
            'organization':'external-b'},timeout=10)
        assert response.status_code == 200
        return response.json()['access_token']
    fingerprints = {}
    for key, tenant in [('a','tenant-a'),('b','tenant-b')]:
        signed = token(key)
        subject,role,resolved = resolve_oidc_identity_with_tenant(signed)
        assert resolved == tenant and subject.startswith('oidc:')
        assert role == ApiRole.OPERATOR
        for claim in (user_claim(tenant,subject),api_claim(tenant,subject,'operator')):
            s.authority.change(claim,enabled=True,expected_version=0,actor='oidc-recipe-provisioner')
        s.headers['oidc-'+key] = {'Authorization':'Bearer '+signed}
        fingerprints[key] = sha256(signed.encode()).hexdigest()
    identifier = 'oidc-'+uuid4().hex
    assert s.request('POST','/workflows/executions','oidc-a',json=s.payload(identifier)).status_code == 201
    assert s.stored(identifier)['metadata']['tenant_id'] == 'tenant-a'
    assert s.request('GET',f'/workflows/executions/{identifier}','oidc-b').status_code == 404
    assert s.request('POST',f'/workflows/executions/{identifier}/start','oidc-b').status_code == 404
    for client in ('foreign','unbound','expired'):
        signed = token(client)
        if client == 'expired':
            exp = jwt.decode(signed,options={'verify_signature':False})['exp']
            time.sleep(max(0,exp-time.time()+.2))
        s.headers['reject'] = {'Authorization':'Bearer '+signed}
        assert s.request('GET',f'/workflows/executions/{identifier}','reject').status_code == 401
        fingerprints[client] = sha256(signed.encode()).hexdigest()
    signed = token('a')
    parts = signed.split('.')
    # Corrupt signed payload while retaining issuer, kid and signature.
    import base64
    payload = json.loads(base64.urlsafe_b64decode(parts[1]+'==='))
    payload['organization'] = 'external-b'
    parts[1] = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    s.headers['forged'] = {'Authorization':'Bearer '+'.'.join(parts)}
    assert s.request('GET',f'/workflows/executions/{identifier}','forged').status_code == 401
    assert s.request('POST',f'/workflows/executions/{identifier}/start','oidc-a').status_code == 202
    s.start('results'); s.start('outbox')
    wait(lambda:s.stored(identifier)['status']=='completed')
    assert set(s.stored(identifier)['context']['outputs']) == {'first','second'}
    assert s.request('GET',f'/workflows/executions/{identifier}','oidc-a').status_code == 200
    (s.dir/'oidc-token-fingerprints.json').write_text(json.dumps(fingerprints))
