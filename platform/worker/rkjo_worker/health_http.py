"""Minimal HTTP health server for RKJO workers."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Protocol


class HealthProvider(Protocol):
    def snapshot(self):
        ...


class HealthHTTPServer:
    """Expose worker health over a minimal stdlib HTTP server."""

    def __init__(
        self,
        health: HealthProvider,
        host: str = "0.0.0.0",
        port: int = 8081,
    ) -> None:
        self.health = health
        self.host = host
        self.port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    def start(self) -> None:
        health = self.health

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                snapshot = health.snapshot()

                if self.path == "/live":
                    payload = {
                        "live": snapshot.live,
                    }
                    status = (
                        HTTPStatus.OK
                        if snapshot.live
                        else HTTPStatus.SERVICE_UNAVAILABLE
                    )

                elif self.path == "/ready":
                    payload = {
                        "ready": snapshot.ready,
                    }
                    status = (
                        HTTPStatus.OK
                        if snapshot.ready
                        else HTTPStatus.SERVICE_UNAVAILABLE
                    )

                elif self.path == "/health":
                    payload = snapshot.as_dict()
                    status = (
                        HTTPStatus.OK
                        if snapshot.live
                        else HTTPStatus.SERVICE_UNAVAILABLE
                    )

                else:
                    payload = {
                        "error": "not_found",
                    }
                    status = HTTPStatus.NOT_FOUND

                body = json.dumps(payload).encode("utf-8")

                self.send_response(status)
                self.send_header(
                    "Content-Type",
                    "application/json",
                )
                self.send_header(
                    "Content-Length",
                    str(len(body)),
                )
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args) -> None:
                return

        self._server = ThreadingHTTPServer(
            (self.host, self.port),
            Handler,
        )

        self._thread = Thread(
            target=self._server.serve_forever,
            name="rkjo-health-http",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server is None:
            return

        self._server.shutdown()
        self._server.server_close()

        if self._thread is not None:
            self._thread.join(timeout=2)

        self._server = None
        self._thread = None
