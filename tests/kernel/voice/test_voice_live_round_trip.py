from types import SimpleNamespace

from rkjo_kernel.voice.live_round_trip import run_round_trip


class Client:
    def __init__(self):
        self.audio = SimpleNamespace(
            transcriptions=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(text="bonjour rkjo", language="fr")
            ),
            speech=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(content=b"generated-audio")
            ),
        )


def test_live_round_trip_pipeline_without_network(tmp_path):
    source = tmp_path / "input.wav"
    target = tmp_path / "output.mp3"
    source.write_bytes(b"audio-fixture")

    text = run_round_trip(source, target, client=Client(), language="fr")

    assert text == "bonjour rkjo"
    assert target.read_bytes() == b"generated-audio"
