"""Real HTTP/process/SQL/AMQP acceptance for L1. No dependency_overrides."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
from uuid import uuid4

import httpx
import pika
import psycopg
import pytest

from rkjo_api.jwt_auth import create_access_token
from rkjo_api.security import ApiRole
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.workflow.postgres_unit_of_work import PostgreSQLWorkflowUnitOfWork
from rkjo_kernel.workflow.security_authorization import ResultAuthenticator

ROOT = Path(__file__).resolve().parents[2]
DB = os.environ["RKJO_TEST_DATABASE_URL"]
MQ = os.environ["RKJO_TEST_RABBITMQ_URL"]
EVIDENCE = Path(os.environ["RKJO_L1_EVIDENCE"])
assert "@127.0.0.1:" in DB and DB.endswith("/l1_test")


def wait(predicate, timeout=25):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            last = predicate()
            if last:
                return last
        except (httpx.TransportError, psycopg.OperationalError):
            pass
        time.sleep(0.05)
    raise AssertionError(f"Deadline exceeded; last value: {last!r}")


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Stack:
    def __init__(self, name):
        self.name = name + "-" + uuid4().hex[:8]
        self.dir = EVIDENCE / self.name
        self.dir.mkdir(parents=True)
        self.env = dict(os.environ, RKJO_WORKER_HEALTH_HOST="127.0.0.1",
                        RKJO_WORKER_HEALTH_PORT=str(port()))
        self.url = f"http://127.0.0.1:{port()}"
        self.processes, self.logs, self.events = {}, [], []
        self.headers = {key: {"Authorization": "Bearer " + create_access_token(
            subject=user, role=role, tenant_id=tenant)} for key, user, role, tenant in
            [("a", "alice", ApiRole.OPERATOR, "tenant-a"),
             ("b", "bob", ApiRole.OPERATOR, "tenant-b"),
             ("viewer", "reader", ApiRole.VIEWER, "tenant-a"),
             ("unbound", "old", ApiRole.ADMIN, None)]}
        PostgreSQLWorkflowUnitOfWork(DB).initialize_schema()

    def sql(self, query, values=()):
        with psycopg.connect(DB) as conn:
            cursor = conn.execute(query, values)
            return cursor.fetchall() if cursor.description else []

    def start(self, service, fault=False):
        module = {"worker": "rkjo_worker.main", "results": "rkjo_worker.workflow_result_consumer",
                  "outbox": "rkjo_worker.outbox_worker"}
        if service == "api":
            cmd = [sys.executable, "-m", "uvicorn", "rkjo_api.main:app", "--host", "127.0.0.1",
                   "--port", self.url.rsplit(":", 1)[1]]
        elif fault:
            cmd = [sys.executable, str(ROOT / "tests/l1/process_fault.py")]
            self.env["L1_ACK_BARRIER"] = str(self.dir / "ack-barrier")
        else:
            cmd = [sys.executable, "-m", module[service]]
        log = (self.dir / f"{service}-{len(self.logs)}.log").open("w")
        self.logs.append(log)
        self.processes[service] = subprocess.Popen(cmd, cwd=ROOT, env=self.env,
                                                  stdout=log, stderr=subprocess.STDOUT)
        self.events.append({"start": service, "pid": self.processes[service].pid, "command": cmd})
        def service_ready(url):
            if self.processes[service].poll() is not None:
                raise RuntimeError(f"L1 {service} process exited before readiness; see its local log.")
            return httpx.get(url).status_code == 200
        if service == "api":
            wait(lambda: service_ready(self.url + "/health"))
        elif service == "worker":
            wait(lambda: service_ready("http://127.0.0.1:" + self.env["RKJO_WORKER_HEALTH_PORT"] + "/ready"))

    def stop(self, service, kill=False):
        process = self.processes.pop(service, None)
        if process is None:
            return
        process.send_signal(signal.SIGKILL if kill else signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        self.events.append({"stop": service, "pid": process.pid, "exit": process.returncode})

    def request(self, method, path, identity="a", **kwargs):
        response = httpx.request(method, self.url + path, headers=self.headers.get(identity, {}),
                                 timeout=15, **kwargs)
        self.events.append({"http": method, "path": path, "identity": identity,
                            "status": response.status_code, "body": response.json()})
        return response

    def payload(self, identifier):
        return {"workflow_id": "l1-neutral", "name": "L1 neutral", "execution_id": identifier,
                "input_data": {"text": "neutral reusable workflow"}, "steps": [
                    {"step_id": "first", "name": "First", "capability_name": "platform_task", "position": 0},
                    {"step_id": "second", "name": "Second", "agent_name": "rkjo.platform.worker", "position": 1}]}

    def create(self):
        identifier = "l1-" + uuid4().hex
        assert self.request("POST", "/workflows/executions", json=self.payload(identifier)).status_code == 201
        return identifier

    def start_execution(self, identifier, expected=202):
        response = self.request("POST", f"/workflows/executions/{identifier}/start")
        assert response.status_code == expected, response.text
        return response

    def stored(self, identifier):
        return self.sql("SELECT payload FROM workflow_executions WHERE execution_id=%s", (identifier,))[0][0]

    def intents(self, identifier):
        return self.sql("SELECT message_payload, published_at FROM workflow_outbox "
                        "WHERE message_payload->'metadata'->>'workflow_execution_id'=%s ORDER BY created_at",
                        (identifier,))

    def complete(self, identifier):
        wait(lambda: self.stored(identifier)["status"] == "completed")
        value = self.stored(identifier)
        outputs = value["context"]["outputs"]
        assert set(outputs) == {"first", "second"}
        assert outputs["second"]["payload"]["outputs"]["first"] == outputs["first"]
        assert len(self.intents(identifier)) == 2
        wait(lambda: all(row[1] is not None for row in self.intents(identifier)))
        assert self.request("GET", f"/workflows/executions/{identifier}").json()["status"] == "completed"
        (self.dir / f"{identifier}.json").write_text(json.dumps(value, indent=2))
        return value

    def publish(self, queue, message):
        with pika.BlockingConnection(pika.URLParameters(MQ)) as conn:
            ch = conn.channel()
            ch.confirm_delivery()
            ch.queue_declare(queue=queue, durable=True)
            ch.basic_publish(exchange="", routing_key=queue, body=message.model_dump_json(),
                             properties=pika.BasicProperties(delivery_mode=2), mandatory=True)

    def take(self, queue):
        with pika.BlockingConnection(pika.URLParameters(MQ)) as conn:
            ch = conn.channel()
            ch.queue_declare(queue=queue, durable=True)
            method, _, body = ch.basic_get(queue, auto_ack=True)
            return AgentMessage.model_validate_json(body) if method else None

    def close(self):
        for service in list(self.processes):
            self.stop(service)
        for log in self.logs:
            log.close()
        (self.dir / "timeline.json").write_text(json.dumps(self.events, indent=2))


@pytest.fixture
def stack(request):
    value = Stack(request.node.name)
    try:
        value.start("api")
        value.start("worker")
        yield value
    finally:
        value.close()


def test_two_steps_restart_and_insert_only(stack):
    stack.start("results")
    stack.start("outbox")
    identifier = stack.create()
    stack.start_execution(identifier)
    value = stack.complete(identifier)
    for service in ("api", "worker", "results", "outbox"):
        stack.stop(service)
        stack.start(service)
    assert stack.complete(identifier) == value
    assert stack.request("POST", "/workflows/executions", json=stack.payload(identifier)).status_code == 422
    assert stack.stored(identifier) == value
    meta = value["context"]["metadata"]
    assert meta["tenant_id"] == "tenant-a" and meta["user_id"] == "alice"
    assert meta["policy_context"] == {"api_role": "operator"}
    for message, _ in stack.intents(identifier):
        assert all(message["metadata"][k] == meta[k] for k in meta)
        assert message["target"] == "rkjo.platform.worker"


def test_concurrent_start_crash_before_publish(stack):
    identifier = stack.create()
    barrier = threading.Barrier(2)
    def start():
        barrier.wait()
        return stack.request("POST", f"/workflows/executions/{identifier}/start").status_code
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(start) for _ in range(2)]
        assert sorted(f.result() for f in futures) == [202, 409]
    assert len(stack.intents(identifier)) == 1
    assert stack.intents(identifier)[0][1] is None
    stack.stop("api", kill=True)  # SQL commit observed, publisher not yet started.
    stack.start("api")
    stack.start("results")
    stack.start("outbox")
    stack.complete(identifier)


def test_absent_worker_and_sql_rollback_leave_pending(stack):
    stack.stop("worker", kill=True)
    time.sleep(3.2)  # Lease expiration, not an optimistic cleanup of the registry.
    identifier = stack.create()
    stack.start_execution(identifier, expected=503)
    assert stack.stored(identifier)["status"] == "pending"
    assert stack.intents(identifier) == []
    stack.start("worker")
    # Real DB fault after insertion, in the same transaction as RUNNING.
    stack.sql("""CREATE OR REPLACE FUNCTION l1_abort_outbox() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'L1 injected rollback'; END $$;
      CREATE TRIGGER l1_abort AFTER INSERT ON workflow_outbox
      FOR EACH ROW EXECUTE FUNCTION l1_abort_outbox();""")
    try:
        stack.start_execution(identifier, expected=503)
        assert stack.stored(identifier)["status"] == "pending"
        assert stack.stored(identifier)["current_step_id"] is None
        assert stack.intents(identifier) == []
    finally:
        stack.sql("DROP TRIGGER l1_abort ON workflow_outbox; DROP FUNCTION l1_abort_outbox()")
    stack.start("results")
    stack.start("outbox")
    stack.start_execution(identifier)
    stack.complete(identifier)


def test_http_authority_refusals(stack):
    identifier = stack.create()
    before = stack.stored(identifier)
    for identity, code in [("b", 404), ("unbound", 403), ("anonymous", 401)]:
        for method, suffix in [("GET", ""), ("POST", "/start")]:
            assert stack.request(method, f"/workflows/executions/{identifier}{suffix}", identity).status_code == code
    assert stack.request("POST", f"/workflows/executions/{identifier}/start", "viewer").status_code == 403
    assert stack.request("POST", "/workflows/executions", "viewer", json=stack.payload("no-viewer")).status_code == 403
    for meta in [{"tenant_id": "tenant-b"}, {"user_id": "mallory"}, {"role": "admin"},
                 {"policy_context": {"api_role": "admin"}}, {"mission_id": "forged"}, {"trace_id": "forged"}]:
        payload = stack.payload("l1-forged-" + uuid4().hex)
        payload["metadata"] = meta
        assert stack.request("POST", "/workflows/executions", json=payload).status_code == 403
        assert not stack.sql("SELECT 1 FROM workflow_executions WHERE execution_id=%s", (payload["execution_id"],))
    body = stack.payload("l1-forged-body")
    body["user_id"] = "mallory"
    assert stack.request("POST", "/workflows/executions", json=body).status_code == 422
    body = stack.payload("l1-forged-step")
    body["steps"][0]["metadata"] = {"policy_context": {"api_role": "admin"}}
    assert stack.request("POST", "/workflows/executions", json=body).status_code == 403
    assert stack.stored(identifier) == before and stack.intents(identifier) == []
    stack.sql("UPDATE workflow_executions SET payload=jsonb_set(jsonb_set(payload, '{metadata}', '{}'::jsonb), "
              "'{context,metadata}', '{}'::jsonb) WHERE execution_id=%s", (identifier,))
    assert stack.request("GET", f"/workflows/executions/{identifier}").status_code == 404
    stack.start_execution(identifier, expected=404)


def test_forged_requests_results_then_legitimate_retry(stack):
    identifier = stack.create()
    stack.start_execution(identifier)
    original = AgentMessage.model_validate(stack.intents(identifier)[0][0])
    baseline = stack.stored(identifier)
    # Attacker knows legitimate message ID: rejection must not poison it.
    for key, value in [("tenant_id", "tenant-b"), ("user_id", "mallory"),
                       ("policy_context", {"api_role": "admin"}), ("reply_queue", "attacker.queue")]:
        forged = original.model_copy(deep=True)
        forged.metadata[key] = value
        stack.publish("rkjo.platform.worker", forged)
        wait(lambda: stack.take("rkjo.platform.worker.dlq"))
        assert stack.stored(identifier) == baseline
    forged = original.model_copy(deep=True)
    forged.payload["input_data"] = {"forged": True}
    stack.publish("rkjo.platform.worker", forged)
    wait(lambda: stack.take("rkjo.platform.worker.dlq"))
    assert stack.take("rkjo.workflow.results") is None  # No forged failure result.
    # Run authentic request, capture worker's signed result before the consumer.
    stack.publish("rkjo.platform.worker", original)
    legitimate = wait(lambda: stack.take("rkjo.workflow.results"))
    stack.start("results")
    signer = ResultAuthenticator.from_env()
    for key, value in [("tenant_id", "tenant-b"), ("workflow_step_id", "unknown"),
                       ("user_id", "mallory")]:
        forged = legitimate.model_copy(deep=True)
        forged.metadata[key] = value
        signer.sign(forged)  # Even an authenticated internal peer cannot cross authority.
        stack.publish("rkjo.workflow.results", forged)
        wait(lambda: stack.take("rkjo.workflow.results.dlq"))
        assert stack.stored(identifier) == baseline
    for key, value in [("source", "untrusted.agent"), ("target", "other.workflow")]:
        forged = legitimate.model_copy(deep=True)
        setattr(forged, key, value)
        signer.sign(forged)
        stack.publish("rkjo.workflow.results", forged)
        wait(lambda: stack.take("rkjo.workflow.results.dlq"))
        assert stack.stored(identifier) == baseline
    forged = legitimate.model_copy(deep=True)
    forged.payload["result"] = {"forged": True}  # No signing key: HMAC rejects content forgery.
    stack.publish("rkjo.workflow.results", forged)
    wait(lambda: stack.take("rkjo.workflow.results.dlq"))
    assert stack.stored(identifier) == baseline
    stack.publish("rkjo.workflow.results", legitimate)
    stack.start("outbox")
    stack.complete(identifier)


def test_commit_before_ack_redelivery_and_duplicate_result(stack):
    stack.start("results", fault=True)
    stack.start("outbox")
    identifier = stack.create()
    stack.start_execution(identifier)
    wait(lambda: (stack.dir / "ack-barrier").exists())
    assert "first" in stack.stored(identifier)["context"]["outputs"]
    first_request_id = stack.intents(identifier)[0][0]["message_id"]
    assert stack.sql("SELECT count(*) FROM workflow_inbox")[0][0] >= 1
    stack.stop("results", kill=True)  # No ACK was sent. Broker requeues same delivery.
    stack.start("results")
    final = stack.complete(identifier)
    result_logs = "".join(p.read_text() for p in stack.dir.glob("results-*.log"))
    assert "redelivered=True" in result_logs
    # Replaying the original task after completion must not run it again.
    original = AgentMessage.model_validate(stack.intents(identifier)[0][0])
    assert original.message_id == first_request_id
    stack.publish("rkjo.platform.worker", original)
    def received_twice():
        logs = "".join(p.read_text() for p in stack.dir.glob("worker-*.log"))
        return logs if logs.count(f"AgentMessage '{original.message_id}' received") >= 2 else None
    logs = wait(received_twice)
    assert logs.count(f"processed message '{original.message_id}' successfully") == 1
    assert stack.stored(identifier) == final
    assert len(stack.intents(identifier)) == 2


def test_legitimate_broker_retry_after_result_transaction_failure(stack):
    # PostgreSQL sequences are not rolled back: fail only the first real INSERT.
    stack.sql("""CREATE SEQUENCE l1_retry_seq;
      CREATE FUNCTION l1_retry_inbox() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF nextval('l1_retry_seq') = 1 THEN RAISE EXCEPTION 'L1 transient SQL failure'; END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER l1_retry BEFORE INSERT ON workflow_inbox
      FOR EACH ROW EXECUTE FUNCTION l1_retry_inbox();""")
    try:
        stack.start("results")
        stack.start("outbox")
        identifier = stack.create()
        stack.start_execution(identifier)
        stack.complete(identifier)
        assert stack.sql("SELECT last_value FROM l1_retry_seq")[0][0] >= 3
        result_logs = "".join(p.read_text() for p in stack.dir.glob("results-*.log"))
        assert "attempt 2/3" in result_logs
        assert stack.take("rkjo.workflow.results.dlq") is None
    finally:
        stack.sql("DROP TRIGGER l1_retry ON workflow_inbox; DROP FUNCTION l1_retry_inbox(); DROP SEQUENCE l1_retry_seq")
