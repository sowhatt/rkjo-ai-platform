import base64

from rkjo_api.voice import VoiceWebSocketGateway


class Socket:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.accepted = False
        self.sent = []
        self.closed = []
    async def accept(self):
        self.accepted = True
    async def receive_json(self):
        try:
            return next(self.messages)
        except StopIteration:
            raise StopAsyncIteration
    async def send_json(self, payload):
        self.sent.append(payload)
    async def close(self, code=1000):
        self.closed.append(code)


def message(**overrides):
    value = {
        "type": "audio.chunk",
        "data": base64.b64encode(b"pcm").decode("ascii"),
        "sequence": 0,
        "mime_type": "audio/pcm",
        "tenant_id": "tenant-a",
        "session_id": "session-1",
        "mission_id": "mission-1",
        "trace_id": "trace-1",
        "is_final": True,
    }
    value.update(overrides)
    return value


async def test_gateway_accepts_and_dispatches_authenticated_audio():
    socket = Socket([message()])
    received = []
    async def on_audio(chunk):
        received.append(chunk)
    gateway = VoiceWebSocketGateway(
        websocket=socket, tenant_id="tenant-a", session_id="session-1",
        mission_id="mission-1", trace_id="trace-1", on_audio=on_audio,
    )
    await gateway.run()
    assert socket.accepted is True
    assert len(received) == 1
    assert received[0].data == b"pcm"
    assert socket.closed == [1000]


async def test_gateway_fails_closed_on_cross_tenant_audio():
    socket = Socket([message(tenant_id="tenant-b")])
    received = []
    async def on_audio(chunk):
        received.append(chunk)
    gateway = VoiceWebSocketGateway(
        websocket=socket, tenant_id="tenant-a", session_id="session-1",
        mission_id="mission-1", trace_id="trace-1", on_audio=on_audio,
    )
    await gateway.run()
    assert received == []
    assert socket.sent[-1]["type"] == "error"
    assert "tenant_id" in socket.sent[-1]["error"]
    assert socket.closed == [1008]


async def test_gateway_fails_closed_on_trace_conflict():
    socket = Socket([message(trace_id="wrong")])
    async def on_audio(chunk):
        raise AssertionError("must not dispatch")
    gateway = VoiceWebSocketGateway(
        websocket=socket, tenant_id="tenant-a", session_id="session-1",
        mission_id="mission-1", trace_id="trace-1", on_audio=on_audio,
    )
    await gateway.run()
    assert socket.closed == [1008]


async def test_gateway_rejects_invalid_wire_message():
    socket = Socket([{"type": "wrong"}])
    async def on_audio(chunk):
        raise AssertionError("must not dispatch")
    gateway = VoiceWebSocketGateway(
        websocket=socket, tenant_id="tenant-a", session_id="session-1",
        mission_id=None, trace_id=None, on_audio=on_audio,
    )
    await gateway.run()
    assert socket.sent[-1]["type"] == "error"
    assert socket.closed == [1008]
