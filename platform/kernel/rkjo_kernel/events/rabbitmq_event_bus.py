import pika

from rkjo_kernel.config.settings import settings
from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.logging.logger import get_logger


class RabbitMQEventBus(EventBus):
    """
    Implémentation RabbitMQ du bus d'événements du RKJO AI Kernel.

    Pourquoi cette classe ?

    Le reste de notre plateforme ne doit pas connaître les détails techniques
    de RabbitMQ. Les agents et l'orchestrateur communiqueront uniquement avec
    le contrat générique EventBus.

    Cela nous permettra plus tard de créer d'autres implémentations :

    - KafkaEventBus
    - RedisEventBus
    - InMemoryEventBus

    sans réécrire les agents IA.
    """

    def __init__(self) -> None:
        """
        Initialise la connexion à RabbitMQ.

        À la création de RabbitMQEventBus :

        1. On lit l'URL RabbitMQ depuis la configuration.
        2. On crée les paramètres de connexion.
        3. On ouvre une connexion avec RabbitMQ.
        4. On crée un channel.

        Le channel est le canal utilisé pour publier et recevoir des messages.
        """

        self.logger = get_logger("rkjo.events.rabbitmq")

        self.logger.info("Connecting to RabbitMQ...")

        parameters = pika.URLParameters(settings.rabbitmq_url)

        self.connection = pika.BlockingConnection(parameters)

        self.channel = self.connection.channel()

        self.logger.info("Connected to RabbitMQ successfully.")

    def publish(self, queue_name: str, message: str) -> None:
        """
        Publie un message dans une queue RabbitMQ.

        Exemple :

        queue_name = "agent.climat"

        message = "Analyse le risque de sécheresse dans l'Eure"

        RabbitMQ conservera le message jusqu'à ce qu'un consommateur
        — par exemple l'Agent Climat — le récupère.
        """

        # On crée la queue si elle n'existe pas encore.
        #
        # durable=True signifie que la définition de la queue peut survivre
        # à un redémarrage de RabbitMQ.
        self.channel.queue_declare(
            queue=queue_name,
            durable=True,
        )

        # On publie le message.
        #
        # exchange="" :
        # utilisation de l'exchange direct par défaut de RabbitMQ.
        #
        # routing_key=queue_name :
        # le message est routé vers la queue portant ce nom.
        self.channel.basic_publish(
            exchange="",
            routing_key=queue_name,
            body=message.encode("utf-8"),
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent
            ),
        )

        self.logger.info(
            "Message published to queue '%s'.",
            queue_name,
        )

    def consume(self, queue_name: str, callback) -> None:
        """
        Écoute continuellement une queue RabbitMQ.

        Lorsqu'un message arrive :

        1. RabbitMQ appelle _on_message.
        2. Le message est décodé.
        3. Notre callback métier est exécuté.
        4. Si tout réussit, le message est acquitté avec basic_ack.

        Exemple futur :

        RabbitMQ
            ↓
        queue agent.climat
            ↓
        Agent Climat
            ↓
        analyse météo
        """

        self.channel.queue_declare(
            queue=queue_name,
            durable=True,
        )

        def _on_message(channel, method, properties, body) -> None:
            """
            Fonction interne appelée automatiquement par pika
            lorsqu'un message est reçu.
            """

            message = body.decode("utf-8")

            self.logger.info(
                "Message received from queue '%s'.",
                queue_name,
            )

            try:
                # On transmet le message à la logique métier.
                callback(message)

                # ACK = accusé de réception.
                #
                # On confirme à RabbitMQ que le traitement a réussi.
                # RabbitMQ peut alors supprimer le message de la queue.
                channel.basic_ack(
                    delivery_tag=method.delivery_tag
                )

            except Exception:
                self.logger.exception(
                    "Error while processing message from queue '%s'.",
                    queue_name,
                )

                # NACK = traitement échoué.
                #
                # Pour cette première version, on remet le message dans la queue.
                # Plus tard, nous ajouterons :
                # - retry limité ;
                # - backoff ;
                # - Dead Letter Queue.
                channel.basic_nack(
                    delivery_tag=method.delivery_tag,
                    requeue=True,
                )

        # QoS : un consommateur ne reçoit qu'un seul message non acquitté
        # à la fois.
        #
        # C'est utile pour éviter de surcharger un agent IA avec trop
        # de tâches simultanées.
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

        # Cette instruction bloque le processus et attend les messages.
        self.channel.start_consuming()

    def close(self) -> None:
        """
        Ferme proprement la connexion RabbitMQ.

        Pourquoi ?

        Une connexion réseau doit toujours être libérée correctement,
        notamment lors de l'arrêt du Kernel ou d'un agent.
        """

        if self.connection and self.connection.is_open:
            self.connection.close()

            self.logger.info(
                "RabbitMQ connection closed successfully."
            )