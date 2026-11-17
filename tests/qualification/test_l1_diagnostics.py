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
