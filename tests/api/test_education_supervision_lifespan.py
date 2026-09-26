import importlib
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.anyio


async def test_supervision_consumer_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv(
        "RKJO_EDUCATION_SUPERVISION_CONSUMER_ENABLED",
        raising=False,
    )
    import rkjo_api.main as main_module

    with patch.object(
        main_module,
        "get_event_bus",
    ) as get_event_bus:
        async with main_module.app.router.lifespan_context(main_module.app):
            pass

    assert fake_bus.stopped is True
    assert fake_bus.closed is True

    get_event_bus.assert_not_called()


async def test_supervision_consumer_can_be_enabled(monkeypatch):
    monkeypatch.setenv(
        "RKJO_EDUCATION_SUPERVISION_CONSUMER_ENABLED",
        "true",
    )
    import rkjo_api.main as main_module
    importlib.reload(main_module)

    class FakeBus:
        def __init__(self):
            self.stopped = False
            self.closed = False

        def consume(self, queue_name, callback):
            return None

        def stop_consuming(self):
            self.stopped = True

        def close(self):
            self.closed = True

    fake_bus = FakeBus()
    with patch.object(
        main_module,
        "get_event_bus",
        return_value=fake_bus,
    ):
        async with main_module.app.router.lifespan_context(main_module.app):
            pass
