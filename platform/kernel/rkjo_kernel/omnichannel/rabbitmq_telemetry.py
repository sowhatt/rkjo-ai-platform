"""OMNI-016.4.3.2 — read-only RabbitMQ Management telemetry.

Infrastructure-only metrics. Never expose broker queue counts through the
tenant-scoped /omnichannel/dashboard endpoint: a shared queue aggregates tenants.
Only explicit queue allowlists are queried; no message contents are retrieved.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import base64
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


_NAME = re.compile(r"^[a-zA-Z0-9_.-]{1,128}$")


@dataclass(frozen=True, slots=True)
class QueueTelemetry:
    name: str
    ready: int
    unacked: int
    consumers: int
    total: int
    is_dlq: bool


def _counter(obj: dict, key: str) -> int:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("Invalid RabbitMQ Management counter.")
    return value


class RabbitMQQueueProbe:
    def __init__(self, *, base_url: str, username: str, password: str,
                 vhost: str, queue_names: list[str], timeout_seconds: float = 3.0):
        target = urlsplit(base_url)
        if (target.scheme not in ("http", "https") or not target.netloc
                or target.username is not None or target.password is not None
                or target.query or target.fragment or target.path not in ("", "/")):
            raise ValueError("Invalid RabbitMQ Management origin.")
        if not username or not password or not vhost:
            raise ValueError("Management credentials and vhost required.")
        if not queue_names or len(queue_names) > 32 or len(set(queue_names)) != len(queue_names):
            raise ValueError("Explicit nonduplicate queue allowlist required.")
        if any(not _NAME.fullmatch(n) for n in queue_names):
            raise ValueError("Invalid RabbitMQ queue name.")
        if not 0 < timeout_seconds <= 10:
            raise ValueError("Invalid probe timeout.")
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.vhost = vhost
        self.queue_names = tuple(queue_names)
        self.timeout_seconds = timeout_seconds

    def snapshot(self) -> tuple[QueueTelemetry, ...]:
        authorization = base64.b64encode(
            f"{self.username}:{self.password}".encode("utf-8")
        ).decode("ascii")
        result = []
        for name in self.queue_names:
            path = f"/api/queues/{quote(self.vhost, safe='')}/{quote(name, safe='')}"
            req = Request(
                self.base_url + path,
                headers={"Authorization": "Basic " + authorization,
                         "Accept": "application/json"},
                method="GET",
            )
            try:
                with urlopen(req, timeout=self.timeout_seconds) as response:
                    if response.status != 200:
                        raise RuntimeError("Broker telemetry unavailable.")
                    if "application/json" not in response.headers.get("Content-Type", ""):
                        raise ValueError("Invalid broker response type.")
                    payload = response.read(65537)
                    if len(payload) > 65536:
                        raise ValueError("Broker response exceeded limit.")
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                # Do not propagate endpoints, Authorization or raw response text.
                raise RuntimeError("Broker telemetry unavailable.") from None
            try:
                data = json.loads(payload)
                if not isinstance(data, dict) or data.get("name") != name:
                    raise ValueError("Unexpected RabbitMQ queue.")
                ready = _counter(data, "messages_ready")
                unacked = _counter(data, "messages_unacknowledged")
                consumers = _counter(data, "consumers")
                total = _counter(data, "messages")
                if total != ready + unacked:
                    raise ValueError("Inconsistent RabbitMQ counters.")
            except (ValueError, TypeError, UnicodeDecodeError) as exc:
                raise RuntimeError("Invalid broker telemetry.") from None
            result.append(QueueTelemetry(name,ready,unacked,consumers,total,
                                         name.endswith(".dlq")))
        return tuple(result)


def sanitized_snapshot(queues: tuple[QueueTelemetry, ...]) -> dict:
    return {
        "queues": [asdict(q) for q in queues],
        "totals": {
            "ready": sum(q.ready for q in queues),
            "unacked": sum(q.unacked for q in queues),
            "dlq": sum(q.total for q in queues if q.is_dlq),
        },
        "scope": "infrastructure",
    }
