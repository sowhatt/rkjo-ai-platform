"""Run tests only against the dedicated compose.l1.yml project.

Usage: python scripts/l1_test.py --project rkjo-l1-20261114 [pytest arguments]
The caller starts Compose explicitly. No shared services or .env are used.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def dedicated_ports(output, project):
    """Select published service ports, never Docker's first exposed port.

    Compose versions can include unpublished image ports (PublishedPort=0),
    notably RabbitMQ's Erlang/management ports, before its AMQP publisher.
    """
    decoded = [json.loads(line) for line in output.splitlines() if line.strip()]
    rows = decoded[0] if len(decoded) == 1 and isinstance(decoded[0], list) else decoded
    ports = {}
    for row in rows:
        assert row["Project"] == project and row["Health"] == "healthy"
        required = {"postgres": 5432, "rabbitmq": 5672}[row["Service"]]
        matches = [p for p in row["Publishers"]
                   if p.get("TargetPort") == required and p.get("URL") == "127.0.0.1"
                   and p.get("PublishedPort", 0) > 0]
        if len(matches) != 1:
            raise ValueError(f"Dedicated localhost publisher required for {row['Service']}:{required}")
        ports[row["Service"]] = matches[0]["PublishedPort"]
    if set(ports) != {"postgres", "rabbitmq"}:
        raise ValueError("Both dedicated PostgreSQL and RabbitMQ services are required.")
    return ports


def environment(project):
    if (ROOT / ".env").exists():
        raise ValueError("The isolated recipe must not contain a .env file.")
    if not project.startswith("rkjo-l1-"):
        raise ValueError("A dedicated rkjo-l1-* project is mandatory.")
    command = ["docker", "compose", "-p", project, "-f", str(ROOT / "compose.l1.yml")]
    ports = dedicated_ports(subprocess.check_output(
        command + ["ps", "--format", "json"], text=True), project)
    env = {k: v for k, v in os.environ.items() if not k.startswith(
        ("RKJO_", "DATABASE", "RABBIT", "OPENAI", "PYTHONPATH"))}
    db = f"postgresql://l1:l1-test-only@127.0.0.1:{ports['postgres']}/l1_test"
    mq = f"amqp://l1:l1-test-only@127.0.0.1:{ports['rabbitmq']}/"
    env.update(RKJO_TEST_DATABASE_URL=db, RKJO_DATABASE_URL=db, DATABASE_URL=db,
               RKJO_TEST_RABBITMQ_URL=mq, RABBITMQ_URL=mq,
               RKJO_WORKFLOW_RESULT_SECRET="l1-only-result-signing-key-12345678901234567890",
               RKJO_JWT_SECRET="l1-only-jwt-signing-key-12345678901234567890",
               RKJO_API_KEY="l1-only-api-key", RKJO_API_TENANT_ID="tenant-a",
               RKJO_WORKER_LEASE_SECONDS="3", RKJO_OUTBOX_POLL_INTERVAL_SECONDS="0.05",
               PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1",
               PYTHONPATH=os.pathsep.join(str(ROOT / p) for p in
                   ("platform/kernel", "platform/api", "platform/worker", "domains/education", ".")),
               RKJO_L1_EVIDENCE=str(ROOT / ".test-results/l1"))
    return env


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    args, pytest_args = parser.parse_known_args()
    env = environment(args.project)
    evidence = Path(env["RKJO_L1_EVIDENCE"])
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "infrastructure.json").write_text(json.dumps({
        "project": args.project, "database_host": "127.0.0.1", "database": "l1_test",
        "base_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "python": sys.version, "pytest_arguments": pytest_args}, indent=2))
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest"] +
        (pytest_args or ["tests/l1", "-q", "--junitxml=.test-results/l1/acceptance.xml"]),
        cwd=ROOT, env=env))
