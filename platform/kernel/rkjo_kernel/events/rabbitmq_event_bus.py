from collections.abc import Callable

import pika

from rkjo_kernel.config.settings import settings
from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.logging.logger import get_logger
from rkjo_kernel.messages.agent_message import AgentMessage


class RabbitMQEventBus(EventBus):
    """
    Implémentation RabbitMQ du bus d'événements du RKJO AI Kernel.

    Pourquoi cette classe ?

    Les agents et l'orchestrateur ne doivent pas dépendre directement
    des détails techniques de RabbitMQ.

    Ils utilisent le contrat EventBus, tandis que cette classe prend en charge :
    - la connexion au broker ;
    - la création des files ;
    - la publication ;
    - la consommation ;
    - les ACK et NACK ;
    - la fermeture propre des connexions.
    """

    def __init__(self) -> None:
        """
        Ouvre une connexion avec RabbitMQ et crée un channel.

        Le channel est le canal logique utilisé pour déclarer les files,
        publier des messages et démarrer des consommateurs.
        """

        self.logger = get_logger("rkjo.events.rabbitmq")

        self.logger.info("Connecting to RabbitMQ...")

        parameters = pika.URLParameters(settings.rabbitmq_url)

        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()

        self.logger.info("Connected to RabbitMQ successfully.")

    def publish(self, queue_name: str, message: str) -> None:
        """
        Publie un message texte dans une file RabbitMQ.

        Cette méthode est conservée pour les tests simples et pour assurer
        une transition progressive vers les AgentMessage structurés.
        """

        self.channel.queue_declare(
            queue=queue_name,
            durable=True,
        )

        self.channel.basic_publish(
            exchange="",
            routing_key=queue_name,
            body=message.encode("utf-8"),
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
                content_type="text/plain",
            ),
        )

        self.logger.info(
            "Message published to queue '%s'.",
            queue_name,
        )

    def consume(
        self,
        queue_name: str,
        callback: Callable[[str], None],
    ) -> None:
        """
        Consomme des messages texte depuis une file RabbitMQ.

        Chaque message correctement traité reçoit un ACK.
        En cas d'erreur, il est temporairement replacé dans la file.
        """

        self.channel.queue_declare(
            queue=queue_name,
            durable=True,
        )

        def _on_message(channel, method, properties, body) -> None:
            message = body.decode("utf-8")

            self.logger.info(
                "Message received from queue '%s'.",
                queue_name,
            )

            try:
                callback(message)

                channel.basic_ack(
                    delivery_tag=method.delivery_tag,
                )

            except Exception:
                self.logger.exception(
                    "Error while processing message from queue '%s'.",
                    queue_name,
                )

                channel.basic_nack(
                    delivery_tag=method.delivery_tag,
                    requeue=True,
                )

        self.channel.basic_qos(prefetch_count=1)

        self.channel.basic_consume(
            queue=queue_name,
            on_message_callback=_on_message,
            auto_ack=False,
        )

        self.logger.info(
            "Waiting for messages on queue '%s'...",
            queue_name,
        )

        self.channel.start_consuming()

    def publish_agent_message(
        self,
        queue_name: str,
        message: AgentMessage,
    ) -> None:
        """
        Publie un AgentMessage validé et structuré dans RabbitMQ.

        Pourquoi ?

        Un système multi-agents professionnel ne doit pas échanger uniquement
        du texte libre. Chaque mission doit être traçable et contenir notamment :

        - un message_id ;
        - un correlation_id ;
        - une source ;
        - une cible ;
        - un type de message ;
        - une priorité ;
        - un payload métier ;
        - des métadonnées ;
        - une date de création.
        """

        self.channel.queue_declare(
            queue=queue_name,
            durable=True,
        )

        json_message = message.model_dump_json()

        self.channel.basic_publish(
            exchange="",
            routing_key=queue_name,
            body=json_message.encode("utf-8"),
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
                content_type="application/json",
                message_id=message.message_id,
                correlation_id=message.correlation_id,
                type=message.message_type,
                priority=message.priority,
            ),
        )

        self.logger.info(
            "AgentMessage '%s' published to queue '%s' "
            "with correlation_id '%s'.",
            message.message_id,
            queue_name,
            message.correlation_id,
        )

    def consume_agent_messages(
        self,
        queue_name: str,
        callback: Callable[[AgentMessage], None],
    ) -> None:
        """
        Consomme des AgentMessage depuis RabbitMQ.

        Le JSON reçu est validé par Pydantic avant d'être transmis à l'agent.
        Un message invalide ou mal formé ne doit pas entrer directement
        dans la logique métier.
        """

        self.channel.queue_declare(
            queue=queue_name,
            durable=True,
        )

        def _on_message(channel, method, properties, body) -> None:
            try:
                message = AgentMessage.model_validate_json(body)

                self.logger.info(
                    "AgentMessage '%s' received from queue '%s'.",
                    message.message_id,
                    queue_name,
                )

                callback(message)

                channel.basic_ack(
                    delivery_tag=method.delivery_tag,
                )

            except Exception:
                self.logger.exception(
                    "Error while processing AgentMessage from queue '%s'.",
                    queue_name,
                )

                channel.basic_nack(
                    delivery_tag=method.delivery_tag,
                    requeue=True,
                )

        self.channel.basic_qos(prefetch_count=1)

        self.channel.basic_consume(
            queue=queue_name,
            on_message_callback=_on_message,
            auto_ack=False,
        )

        self.logger.info(
            "Waiting for AgentMessages on queue '%s'...",
            queue_name,
        )

        self.channel.start_consuming()

    def close(self) -> None:
        """
        Ferme proprement la connexion RabbitMQ.

        Cette méthode sera appelée à l'arrêt du Kernel, d'un agent ou d'un test.
        """

        if self.connection and self.connection.is_open:
            self.connection.close()

            self.logger.info(
                "RabbitMQ connection closed successfully."
            )