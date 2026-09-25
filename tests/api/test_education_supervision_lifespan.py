import importlib
from unittest.mock import patch


def test_supervision_consumer_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv(
        "RKJO_EDUCATION_SUPERVISION_CONSUMER_ENABLED",
        raising=False,
    )
    import rkjo_api.main as main_module

    with patch.object(
        main_module,
        "get_event_bus",
    ) as get_event_bus:
        with main_module.app.router.lifespan_context(main_module.app):
            pass

    get_event_bus.assert_not_called()


def test_supervision_consumer_can_be_enabled(monkeypatch):
    monkeypatch.setenv(
        "RKJO_EDUCATION_SUPERVISION_CONSUMER_ENABLED",
        "true",
    )
    import rkjo_api.main as main_module
    importlib.reload(main_module)

    class FakeBus:
        def consume(self, queue_name, callback):
            return None

        def close(self):
            return None

    fake_bus = FakeBus()
    with patch.object(
        main_module,
        "get_event_bus",
        return_value=fake_bus,
    ):
        with main_module.app.router.lifespan_context(main_module.app):
            pass
