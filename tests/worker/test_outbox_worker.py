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


def test_outbox_worker_marks_ready_after_successful_cycle() -> None:
    from rkjo_worker.health import WorkerHealth

    health = WorkerHealth(
        service_name="outbox-worker"
    )

    observations = []

    class Publisher:
        def publish_pending(
            self,
            *,
            limit=100,
        ):
            return 0

    worker = OutboxWorker(
        publisher=Publisher(),
        health=health,
        sleep_fn=lambda _delay: (
            observations.append(
                health.snapshot()
            ),
            worker.stop(),
        ),
    )

    worker.run()

    assert len(observations) == 1

    snapshot = observations[0]

    assert snapshot.live is True
    assert snapshot.ready is True
    assert snapshot.status == "ready"
    assert snapshot.last_error is None

    stopped = health.snapshot()

    assert stopped.live is False
    assert stopped.ready is False
    assert stopped.status == "stopped"


def test_outbox_worker_marks_not_ready_on_failure() -> None:
    from rkjo_worker.health import WorkerHealth

    health = WorkerHealth(
        service_name="outbox-worker"
    )

    observations = []

    class Publisher:
        def publish_pending(
            self,
            *,
            limit=100,
        ):
            raise RuntimeError(
                "simulated outbox failure"
            )

    worker = OutboxWorker(
        publisher=Publisher(),
        health=health,
        sleep_fn=lambda _delay: (
            observations.append(
                health.snapshot()
            ),
            worker.stop(),
        ),
    )

    worker.run()

    assert len(observations) == 1

    snapshot = observations[0]

    assert snapshot.live is True
    assert snapshot.ready is False
    assert snapshot.status == "not_ready"
    assert snapshot.last_error == (
        "simulated outbox failure"
    )


def test_outbox_worker_recovers_readiness_after_failure() -> None:
    from rkjo_worker.health import WorkerHealth

    health = WorkerHealth(
        service_name="outbox-worker"
    )

    observations = []

    class Publisher:
        def __init__(self) -> None:
            self.calls = 0

        def publish_pending(
            self,
            *,
            limit=100,
        ):
            self.calls += 1

            if self.calls == 1:
                raise RuntimeError(
                    "temporary outbox failure"
                )

            return 0

    publisher = Publisher()

    def sleep_and_observe(_delay):
        observations.append(
            health.snapshot()
        )

        if publisher.calls >= 2:
            worker.stop()

    worker = OutboxWorker(
        publisher=publisher,
        health=health,
        sleep_fn=sleep_and_observe,
    )

    worker.run()

    assert publisher.calls == 2
    assert len(observations) == 2

    failed = observations[0]

    assert failed.live is True
    assert failed.ready is False
    assert failed.last_error == (
        "temporary outbox failure"
    )

    recovered = observations[1]

    assert recovered.live is True
    assert recovered.ready is True
    assert recovered.status == "ready"
    assert recovered.last_error is None


def test_outbox_worker_cannot_become_ready_after_stop() -> None:
    from rkjo_worker.health import WorkerHealth

    health = WorkerHealth(
        service_name="outbox-worker"
    )

    class Publisher:
        def publish_pending(
            self,
            *,
            limit=100,
        ):
            worker.stop()
            return 0

    worker = OutboxWorker(
        publisher=Publisher(),
        health=health,
        sleep_fn=lambda _delay: None,
    )

    worker.run()

    snapshot = health.snapshot()

    assert snapshot.live is False
    assert snapshot.ready is False
    assert snapshot.status == "stopped"
