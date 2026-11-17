import json
import xml.etree.ElementTree as ET
from scripts.l1_diagnostics import publish, redact


def test_redacts_secrets_preserving_exception_and_valid_junit(tmp_path):
    raw = tmp_path/'raw'
    raw.mkdir()
    secrets = ['unique-env-secret-123', 'l1-test-only', 'l1-only-api-key',
               'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhIn0.signature', 'foreign-password']
    text = 'RuntimeError: connection failed\n'+ ' '.join(secrets[:4])+' postgresql://user:foreign-password@localhost/db'
    suite = ET.Element('testsuite')
    ET.SubElement(ET.SubElement(suite,'testcase'),'error').text = text
    ET.ElementTree(suite).write(raw/'failure.xml',encoding='unicode')
    (raw/'process.log').write_text(text+'\nAuthorization: Bearer abc123\npassword="hidden-password"')
    (raw/'state.json').write_text(json.dumps({'exception':text}))
    public = tmp_path/'public'
    publish(raw,public,{'RKJO_JWT_SECRET':secrets[0]})
    for path in public.iterdir():
        value=path.read_text()
        assert all(secret not in value for secret in secrets+['abc123','hidden-password'])
    assert 'RuntimeError: connection failed' in ET.parse(public/'failure.xml').find('.//error').text
    assert 'RuntimeError' in json.loads((public/'state.json').read_text())['exception']
    assert text in (raw/'process.log').read_text()


def test_redacts_url_credentials_and_bearer_without_environment():
    text='amqp://u:p%40ss@host/ Bearer token-123 api_key="private-value"'
    result=redact(text,{})
    assert 'p%40ss' not in result and 'token-123' not in result and 'private-value' not in result


def test_phase_collector_keeps_setup_call_and_teardown_exceptions(tmp_path):
    import os
    from pathlib import Path
    import subprocess
    import sys
    source = tmp_path/'test_probe.py'
    source.write_text('''import pytest
@pytest.fixture
def setup_error():
    raise RuntimeError("setup-marker")
@pytest.fixture
def teardown_error():
    yield
    raise RuntimeError("teardown-marker")
def test_setup(setup_error): pass
def test_call(): raise ValueError("call-marker")
def test_teardown(teardown_error): pass
''')
    root=Path(__file__).resolve().parents[2]
    evidence=tmp_path/'evidence'
    env=dict(os.environ,RKJO_L1_EVIDENCE=str(evidence),PYTHONPATH=str(root))
    result=subprocess.run([sys.executable,'-m','pytest','-p','tests.l1.conftest',str(source),
                           '-q',f'--junitxml={tmp_path}/junit.xml'],env=env,cwd=tmp_path,
                          stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    assert result.returncode==1,result.stdout
    phases=[json.loads(p.read_text()) for p in (evidence/'pytest-phases').glob('*.json')]
    failed={p['phase']:p for p in phases if p['outcome']=='failed'}
    assert set(failed)=={'setup','call','teardown'}
    for phase in failed:
        assert phase+'-marker' in failed[phase]['exception']
        assert 'Traceback (most recent call last)' in failed[phase]['exception']
    junit=ET.parse(tmp_path/'junit.xml')
    assert len(junit.findall('.//error'))==2 and len(junit.findall('.//failure'))==1
