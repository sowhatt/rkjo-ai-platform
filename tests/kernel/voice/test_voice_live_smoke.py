from pathlib import Path

import pytest

from rkjo_kernel.voice.live_smoke import mime_for_audio


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("sample.wav", "audio/wav"),
        ("sample.mp3", "audio/mpeg"),
        ("sample.m4a", "audio/mp4"),
        ("sample.webm", "audio/webm"),
        ("sample.ogg", "audio/ogg"),
    ],
)
def test_live_smoke_mime_mapping(name, expected):
    assert mime_for_audio(Path(name)) == expected
