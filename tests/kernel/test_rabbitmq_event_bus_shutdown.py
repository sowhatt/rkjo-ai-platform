from unittest.mock import MagicMock

from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus


def _bus_without_connection() -> RabbitMQEventBus:
    bus = RabbitMQEventBus.__new__(RabbitMQEventBus)
    from threading import Event
    bus._stop_requested = Event()
    bus.connection = MagicMock()
    bus.channel = MagicMock()
    bus.channel.is_open = True
    return bus


def test_stop_consuming_only_signals_shutdown() -> None:
    bus = _bus_without_connection()

    bus.stop_consuming()

    assert bus._stop_requested.is_set()
    bus.connection.add_callback_threadsafe.assert_not_called()
    bus.channel.stop_consuming.assert_not_called()


def test_consumer_loop_exits_and_stops_channel_on_owner_thread() -> None:
    bus = _bus_without_connection()

    def process_data_events(*, time_limit):
        assert time_limit == 0.25
        bus.stop_consuming()

    bus.connection.process_data_events.side_effect = process_data_events

    bus._consume_until_stopped()

    bus.connection.process_data_events.assert_called_once_with(time_limit=0.25)
    bus.channel.stop_consuming.assert_called_once_with()
