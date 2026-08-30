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


class FailingThenSuccessfulPublisher:
    def __init__(self) -> None:
        self.calls = 0

    def publish_pending(
        self,
        *,
        limit: int = 100,
    ) -> int:
        self.calls += 1

        if self.calls <= 3:
            raise RuntimeError(
                "simulated publication failure"
            )

        return 0


def test_outbox_worker_applies_bounded_exponential_backoff() -> None:
    publisher = FailingThenSuccessfulPublisher()

    sleeps = []

    worker = OutboxWorker(
        publisher=publisher,
        poll_interval_seconds=0.5,
        retry_initial_seconds=1.0,
        retry_max_seconds=3.0,
        retry_multiplier=2.0,
        sleep_fn=sleeps.append,
    )

    original_sleep = worker.sleep_fn

    def sleep_and_stop(delay):
        original_sleep(delay)

        if publisher.calls >= 4:
            worker.stop()

    worker.sleep_fn = sleep_and_stop

    worker.run()

    assert publisher.calls == 4

    assert sleeps == [
        1.0,
        2.0,
        3.0,
        0.5,
    ]


def test_outbox_worker_resets_backoff_after_success() -> None:
    class Publisher:
        def __init__(self) -> None:
            self.calls = 0

        def publish_pending(
            self,
            *,
            limit: int = 100,
        ) -> int:
            self.calls += 1

            if self.calls in {
                1,
                3,
            }:
                raise RuntimeError(
                    "simulated failure"
                )

            return 1

    publisher = Publisher()
    sleeps = []

    worker = OutboxWorker(
        publisher=publisher,
        retry_initial_seconds=1.0,
        retry_max_seconds=8.0,
        retry_multiplier=2.0,
        sleep_fn=sleeps.append,
    )

    def sleep_and_stop(delay):
        sleeps.append(delay)

        if len(sleeps) == 2:
            worker.stop()

    worker.sleep_fn = sleep_and_stop

    worker.run()

    assert sleeps == [
        1.0,
        1.0,
    ]


def test_outbox_worker_validates_retry_configuration() -> None:
    publisher = FakePublisher()

    try:
        OutboxWorker(
            publisher=publisher,
            retry_initial_seconds=0,
        )
    except ValueError as exc:
        assert (
            str(exc)
            == "retry_initial_seconds must be greater than zero."
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )

    try:
        OutboxWorker(
            publisher=publisher,
            retry_initial_seconds=2,
            retry_max_seconds=1,
        )
    except ValueError as exc:
        assert (
            str(exc)
            == "retry_max_seconds must be greater than or equal "
            "to retry_initial_seconds."
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )

    try:
        OutboxWorker(
            publisher=publisher,
            retry_multiplier=0.5,
        )
    except ValueError as exc:
        assert (
            str(exc)
            == "retry_multiplier must be greater than or equal to one."
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )


def test_outbox_worker_rebuilds_publisher_after_failure() -> None:
    class BrokenPublisher:
        def publish_pending(
            self,
            *,
            limit: int = 100,
        ) -> int:
            raise RuntimeError(
                "simulated broken RabbitMQ connection"
            )

    class RecoveredPublisher:
        def __init__(self) -> None:
            self.calls = 0

        def publish_pending(
            self,
            *,
            limit: int = 100,
        ) -> int:
            self.calls += 1
            return 0

    recovered = RecoveredPublisher()
    rebuild_calls = []

    def publisher_factory():
        rebuild_calls.append(
            "rebuild"
        )
        return recovered

    sleeps = []

    worker = OutboxWorker(
        publisher=BrokenPublisher(),
        publisher_factory=publisher_factory,
        retry_initial_seconds=1.0,
        sleep_fn=sleeps.append,
    )

    def sleep_and_stop(delay):
        sleeps.append(delay)

        if recovered.calls >= 1:
            worker.stop()

    worker.sleep_fn = sleep_and_stop

    worker.run()

    assert rebuild_calls == [
        "rebuild"
    ]

    assert recovered.calls == 1

    assert sleeps == [
        1.0,
        1.0,
    ]


class FailingThenSuccessfulPublisher:
    def __init__(self) -> None:
        self.calls = 0

    def publish_pending(
        self,
        *,
        limit: int = 100,
    ) -> int:
        self.calls += 1

        if self.calls <= 3:
            raise RuntimeError(
                "simulated publication failure"
            )

        return 0


def test_outbox_worker_applies_bounded_exponential_backoff() -> None:
    publisher = FailingThenSuccessfulPublisher()

    sleeps = []

    worker = OutboxWorker(
        publisher=publisher,
        poll_interval_seconds=0.5,
        retry_initial_seconds=1.0,
        retry_max_seconds=3.0,
        retry_multiplier=2.0,
        sleep_fn=sleeps.append,
    )

    original_sleep = worker.sleep_fn

    def sleep_and_stop(delay):
        original_sleep(delay)

        if publisher.calls >= 4:
            worker.stop()

    worker.sleep_fn = sleep_and_stop

    worker.run()

    assert publisher.calls == 4

    assert sleeps == [
        1.0,
        2.0,
        3.0,
        0.5,
    ]


def test_outbox_worker_resets_backoff_after_success() -> None:
    class Publisher:
        def __init__(self) -> None:
            self.calls = 0

        def publish_pending(
            self,
            *,
            limit: int = 100,
        ) -> int:
            self.calls += 1

            if self.calls in {
                1,
                3,
            }:
                raise RuntimeError(
                    "simulated failure"
                )

            return 1

    publisher = Publisher()
    sleeps = []

    worker = OutboxWorker(
        publisher=publisher,
        retry_initial_seconds=1.0,
        retry_max_seconds=8.0,
        retry_multiplier=2.0,
        sleep_fn=sleeps.append,
    )

    def sleep_and_stop(delay):
        sleeps.append(delay)

        if len(sleeps) == 2:
            worker.stop()

    worker.sleep_fn = sleep_and_stop

    worker.run()

    assert sleeps == [
        1.0,
        1.0,
    ]


def test_outbox_worker_validates_retry_configuration() -> None:
    publisher = FakePublisher()

    try:
        OutboxWorker(
            publisher=publisher,
            retry_initial_seconds=0,
        )
    except ValueError as exc:
        assert (
            str(exc)
            == "retry_initial_seconds must be greater than zero."
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )

    try:
        OutboxWorker(
            publisher=publisher,
            retry_initial_seconds=2,
            retry_max_seconds=1,
        )
    except ValueError as exc:
        assert (
            str(exc)
            == "retry_max_seconds must be greater than or equal "
            "to retry_initial_seconds."
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )

    try:
        OutboxWorker(
            publisher=publisher,
            retry_multiplier=0.5,
        )
    except ValueError as exc:
        assert (
            str(exc)
            == "retry_multiplier must be greater than or equal to one."
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )
