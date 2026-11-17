"""Private failure evidence and publication-safe copies for dedicated L1 tests."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import time
import traceback


def timestamp():
    return {"utc": datetime.now(timezone.utc).isoformat(), "monotonic_ns": time.monotonic_ns()}


def sql_snapshot(dsn):
    import psycopg
    queries = {
        "clock": "SELECT clock_timestamp(), current_database(), pg_postmaster_start_time()",
        "registry": "SELECT name,status,updated_at,payload->'metadata'->>'instance_id' FROM agent_registry",
        "workflows": "SELECT execution_id,status,updated_at FROM workflow_executions",
        "outbox": "SELECT count(*),count(published_at) FROM workflow_outbox",
        "connections": "SELECT application_name,state,wait_event_type,wait_event FROM pg_stat_activity WHERE datname=current_database()",
    }
    result = {}
    for name, query in queries.items():
        try:
            with psycopg.connect(dsn, connect_timeout=2, options='-c statement_timeout=2000') as conn:
                result[name] = conn.execute(query).fetchall()
        except Exception:
            result[name] = {"exception": traceback.format_exc()}
    return result


def snapshot(stack, label):
    """Observe before process cleanup; never change readiness thresholds or retry tests."""
    import httpx
    value = {"label": label, "before": timestamp(),
             "sql": sql_snapshot(stack.env['RKJO_TEST_DATABASE_URL']),
             "processes": {k: {"pid": p.pid, "returncode": p.poll()} for k,p in stack.processes.items()},
             "readiness": {}}
    # /health is non-mutating; API /ready initializes schema and is not probed here.
    for service, url in {"api": stack.url+'/health',
                         "worker": 'http://127.0.0.1:'+stack.env['RKJO_WORKER_HEALTH_PORT']+'/ready'}.items():
        try:
            response = httpx.get(url, timeout=1)
            value['readiness'][service] = {"status": response.status_code, "body": response.text}
        except Exception:
            value['readiness'][service] = {"exception": traceback.format_exc()}
    value['after'] = timestamp()
    (stack.dir / f'{label}-{time.monotonic_ns()}.json').write_text(json.dumps(value,default=str,indent=2))


def infrastructure(root, project, output):
    compose = ['docker','compose','-p',project,'-f',str(root/'compose.l1.yml')]
    commands = {
        'compose-state': ['ps','--format','json'],
        'service-logs': ['logs','--no-color','--timestamps'],
        'broker-listeners': ['exec','-T','rabbitmq','rabbitmq-diagnostics','listeners'],
        'broker-queues': ['exec','-T','rabbitmq','rabbitmqctl','list_queues','name','messages_ready','messages_unacknowledged','consumers'],
    }
    for name, args in commands.items():
        try:
            result = subprocess.run(compose+args,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=20)
            value = {"time": timestamp(), "returncode": result.returncode, "output": result.stdout}
        except Exception:
            value = {"time": timestamp(), "exception": traceback.format_exc()}
        (output/f'{name}.json').write_text(json.dumps(value,indent=2))
    for service in ('postgres','rabbitmq'):
        try:
            container = subprocess.check_output(compose+['ps','-q',service],text=True,timeout=10).strip()
            health = subprocess.check_output(['docker','inspect','--format','{{json .State.Health}}',container],text=True,timeout=10)
            value = {'time':timestamp(),'health':json.loads(health)}
        except Exception:
            value = {'time':timestamp(),'exception':traceback.format_exc()}
        (output/f'{service}-health.json').write_text(json.dumps(value,indent=2))


def redact(text, env=None):
    env = env or os.environ
    secrets = [v for k,v in env.items() if any(s in k.upper() for s in
               ('SECRET','PASSWORD','TOKEN','API_KEY','DATABASE_URL','RABBITMQ_URL')) and len(v)>=6]
    secrets += ['l1-test-only','l1-only-api-key',
                'l1-only-result-signing-key-12345678901234567890',
                'l1-only-jwt-signing-key-12345678901234567890']
    for secret in sorted(set(secrets),key=len,reverse=True):
        text = text.replace(secret,'[REDACTED]')
    text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text)
    text = re.sub(r'(?i)([a-z][a-z0-9+.-]*://)[^\s/\"\'<>]*@',r'\1[REDACTED]@',text)
    text = re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+','[REDACTED-JWT]',text)
    text = re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._~+/-]+=*',r'\1[REDACTED]',text)
    text = re.sub(r'(?i)((?:authorization|api[_-]?key|password|secret|access_token|refresh_token)[\"\']?\s*[:=]\s*[\"\']?)[^\s,\"\'<>}]+',r'\1[REDACTED]',text)
    return text


def publish(raw, public, env):
    public.mkdir(parents=True,exist_ok=True)
    count = 0
    for path in sorted(raw.rglob('*')):
        if path.is_file() and path.suffix in {'.log','.json','.xml','.stdout','.txt'}:
            target = public/path.relative_to(raw)
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(redact(path.read_text(errors='replace'),env))
            count += 1
    (public/'publication.json').write_text(json.dumps({'files':count,'redacted':True,'time':timestamp()},indent=2))
