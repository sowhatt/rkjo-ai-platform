from rkjo_worker.outbox_worker import OutboxWorker


class FakePublisher:
    def __init__(self) -> None:
        self.calls = 0

    def publish_pending(
        self,
        *,
        limit: int = 100,
    ) -> int:
        self.calls += 1

        if self.calls == 1:
            return 1

        return 0


def test_outbox_worker_validates_poll_interval() -> None:
    publisher = FakePublisher()

    try:
        OutboxWorker(
            publisher=publisher,
            poll_interval_seconds=0,
        )
    except ValueError as exc:
        assert (
            str(exc)
            == "poll_interval_seconds must be greater than zero."
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )


def test_outbox_worker_validates_batch_size() -> None:
    publisher = FakePublisher()

    try:
        OutboxWorker(
            publisher=publisher,
            batch_size=0,
        )
    except ValueError as exc:
        assert (
            str(exc)
            == "batch_size must be greater than zero."
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )
