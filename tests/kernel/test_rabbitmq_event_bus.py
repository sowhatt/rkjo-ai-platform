from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus


def test_rabbitmq_publish_message():
    event_bus = RabbitMQEventBus()

    event_bus.publish(
        queue_name="rkjo.test",
        message="Premier message RKJO AI Kernel vers RabbitMQ",
    )

    event_bus.close()

    assert True