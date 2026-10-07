import asyncio
import base64

from rkjo_api.voice_streaming import AsyncWebSocketAudioSink
from rkjo_kernel.voice.streaming import AudioChunk


def test_websocket_audio_sink_sends_ordered_chunks_and_interrupt():
    async def scenario():
        sent = []

        async def send_json(payload):
            sent.append(dict(payload))

        sink = AsyncWebSocketAudioSink(send_json=send_json)
        await sink.start()
        sink.send(AudioChunk(
            data=b"abc", sequence=0, mime_type="audio/mpeg",
            tenant_id="tenant-a", session_id="session-1",
            mission_id="mission-1", trace_id="trace-1",
        ))
        sink.send(AudioChunk(
            data=b"def", sequence=1, mime_type="audio/mpeg",
            tenant_id="tenant-a", session_id="session-1",
            mission_id="mission-1", trace_id="trace-1", is_final=True,
        ))
        sink.interrupt(session_id="session-1", tenant_id="tenant-a")
        await sink.drain()
        await sink.close()

        assert [p["type"] for p in sent] == [
            "audio.chunk", "audio.chunk", "audio.interrupted"
        ]
        assert [p.get("sequence") for p in sent[:2]] == [0, 1]
        assert base64.b64decode(sent[0]["data"]) == b"abc"
        assert sent[1]["is_final"] is True
        assert sent[0]["mission_id"] == "mission-1"
        assert sent[0]["trace_id"] == "trace-1"

    asyncio.run(scenario())


def test_websocket_audio_sink_requires_start():
    async def send_json(payload):
        pass

    sink = AsyncWebSocketAudioSink(send_json=send_json)
    chunk = AudioChunk(
        data=b"x", sequence=0, mime_type="audio/mpeg",
        tenant_id="tenant-a", session_id="session-1",
    )
    import pytest
    with pytest.raises(RuntimeError):
        sink.send(chunk)
