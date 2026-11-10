"""Real HTTP + PostgreSQL qualification. No LLM, browser or ingestion claim."""
from contextlib import contextmanager
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from uuid import uuid4

import httpx
import jwt
import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def api_process(database_url, secret):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {**os.environ, 'RKJO_DATABASE_URL': database_url, 'RKJO_JWT_SECRET': secret,
           'RKJO_API_KEY': secrets.token_hex(32),
           'PYTHONPATH': os.pathsep.join(str(ROOT / p) for p in
               ['platform/api', 'platform/kernel', 'platform/worker', 'domains/education', '.'])}
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'rkjo_api.main:app',
        '--host', '127.0.0.1', '--port', str(port)], env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=10) as client:
            for _ in range(150):
                if process.poll() is not None:
                    pytest.fail('Qualification API exited before startup')
                try:
                    client.get('/openapi.json').raise_for_status()
                    break
                except httpx.TransportError:
                    time.sleep(0.1)
            else:
                pytest.fail('Qualification API startup timeout')
            yield client, process
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_course_http_tenants_roles_and_process_restart():
    url = os.getenv('RKJO_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated PostgreSQL test database')
    if 'test' not in conninfo_to_dict(url).get('dbname', '').lower():
        pytest.fail('Dedicated test database required')
    schema = 'qualification_' + uuid4().hex
    secret = secrets.token_hex(32)
    def identity(tenant, role='operator'):
        now = int(time.time())
        token = jwt.encode({'sub': role + '-' + tenant, 'role': role, 'tenant_id': tenant,
                            'iat': now, 'exp': now + 300}, secret, algorithm='HS256')
        return {'Authorization': 'Bearer ' + token}
    a, b, viewer = identity('a'), identity('b'), identity('a', 'viewer')
    payload = dict(course_id='restart-course', title='Qualification A', subject='Maths', level='CE1')
    with psycopg.connect(url) as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')
    scoped = make_conninfo(url, options=f'-c search_path={schema}')
    try:
        with api_process(scoped, secret) as (client, process):
            assert client.get('/education/courses').status_code == 401
            assert client.post('/education/courses', headers=viewer, json=payload).status_code == 403
            assert client.post('/education/courses', headers=a, json=payload).status_code == 201
            assert client.get('/education/courses', headers=b).json() == []
            assert client.get('/education/courses/restart-course', headers=b).status_code == 404
            assert client.post('/education/courses/restart-course/documents', headers=b,
                               json={'document_id': 'attachment-reference'}).status_code == 404
            # Abrupt API death after confirmed commit. No simulated repository replacement.
            process.kill()
            process.wait(timeout=5)
        with api_process(scoped, secret) as (client, _):
            result = client.get('/education/courses/restart-course', headers=a)
            assert result.status_code == 200
            assert result.json()['title'] == payload['title']
            assert client.post('/education/courses', headers=a, json=payload).status_code == 409
            assert len(client.get('/education/courses', headers=a).json()) == 1
            assert client.get('/education/courses/restart-course', headers=b).status_code == 404
    finally:
        with psycopg.connect(url) as conn:
            conn.execute(f'DROP SCHEMA "{schema}" CASCADE')
