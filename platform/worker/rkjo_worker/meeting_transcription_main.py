"""Entrypoint for the dedicated Meeting Intelligence transcription consumer."""

from __future__ import annotations

from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_meeting_intelligence.infrastructure.openai_stt import OpenAIGPTTranscribeProvider
from rkjo_worker.meeting_transcription_worker import (
    TRANSCRIPTION_QUEUE,
    build_default_worker,
)


def main() -> None:
    worker = build_default_worker(OpenAIGPTTranscribeProvider())
    bus = RabbitMQEventBus()
    try:
        bus.consume(TRANSCRIPTION_QUEUE, worker.process_message)
    finally:
        bus.close()


if __name__ == "__main__":
    main()
