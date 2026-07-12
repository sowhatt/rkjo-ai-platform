from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.logging.logger import get_logger


logger = get_logger("rkjo.agents.test_consumer")


def handle_message(message: str) -> None:
    """
    Fonction appelée quand RabbitMQ livre un message à l'agent.

    Pourquoi ?
    C'est ici que, plus tard, un vrai agent fera son travail :
    - Agent Climat ;
    - Agent Sol ;
    - Agent Recherche ;
    - Agent Agronomie.
    """

    logger.info("Agent received mission: %s", message)
    logger.info("Agent processed mission successfully.")


def main() -> None:
    """
    Point d'entrée de l'agent consommateur.

    Il se connecte à RabbitMQ et écoute la queue rkjo.test.
    """

    event_bus = RabbitMQEventBus()

    try:
        event_bus.consume(
            queue_name="rkjo.test",
            callback=handle_message,
        )
    finally:
        event_bus.close()


if __name__ == "__main__":
    main()