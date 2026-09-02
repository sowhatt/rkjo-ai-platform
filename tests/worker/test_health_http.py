import json
from urllib.error import HTTPError
from urllib.request import urlopen

from rkjo_worker.health import WorkerHealth
from rkjo_worker.health_http import HealthHTTPServer


def _get_json(url: str):
    try:
        with urlopen(url, timeout=2) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_live_endpoint_returns_200_for_live_worker():
    health = WorkerHealth("test-worker")
    server = HealthHTTPServer(
        health=health,
        host="127.0.0.1",
        port=0,
    )

    server.start()

    try:
        port = server._server.server_address[1]

        status, payload = _get_json(
            f"http://127.0.0.1:{port}/live"
        )

        assert status == 200
        assert payload == {
            "live": True,
        }

    finally:
        server.stop()


def test_ready_endpoint_returns_503_when_not_ready():
    health = WorkerHealth("test-worker")
    server = HealthHTTPServer(
        health=health,
        host="127.0.0.1",
        port=0,
    )

    server.start()

    try:
        port = server._server.server_address[1]

        status, payload = _get_json(
            f"http://127.0.0.1:{port}/ready"
        )

        assert status == 503
        assert payload == {
            "ready": False,
        }

    finally:
        server.stop()


def test_ready_endpoint_returns_200_when_ready():
    health = WorkerHealth("test-worker")
    health.mark_ready()

    server = HealthHTTPServer(
        health=health,
        host="127.0.0.1",
        port=0,
    )

    server.start()

    try:
        port = server._server.server_address[1]

        status, payload = _get_json(
            f"http://127.0.0.1:{port}/ready"
        )

        assert status == 200
        assert payload == {
            "ready": True,
        }

    finally:
        server.stop()


def test_health_endpoint_returns_snapshot():
    health = WorkerHealth("test-worker")
    health.mark_not_ready("dependency unavailable")

    server = HealthHTTPServer(
        health=health,
        host="127.0.0.1",
        port=0,
    )

    server.start()

    try:
        port = server._server.server_address[1]

        status, payload = _get_json(
            f"http://127.0.0.1:{port}/health"
        )

        assert status == 200
        assert payload == {
            "service_name": "test-worker",
            "live": True,
            "ready": False,
            "status": "not_ready",
            "last_error": "dependency unavailable",
        }

    finally:
        server.stop()


def test_unknown_endpoint_returns_404():
    health = WorkerHealth("test-worker")

    server = HealthHTTPServer(
        health=health,
        host="127.0.0.1",
        port=0,
    )

    server.start()

    try:
        port = server._server.server_address[1]

        status, payload = _get_json(
            f"http://127.0.0.1:{port}/unknown"
        )

        assert status == 404
        assert payload == {
            "error": "not_found",
        }

    finally:
        server.stop()
