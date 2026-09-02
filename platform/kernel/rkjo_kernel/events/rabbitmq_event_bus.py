from collections.abc import Callable

import pika

from rkjo_kernel.config.settings import settings
from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.logging.logger import get_logger
from rkjo_kernel.messages.agent_message import AgentMessage


_DELIVERY_ATTEMPT_HEADER = "x-rkjo-delivery-attempt"
_ORIGINAL_QUEUE_HEADER = "x-rkjo-original-queue"
_FAILURE_TYPE_HEADER = "x-rkjo-failure-type"
_FAILURE_MESSAGE_HEADER = "x-rkjo-failure-message"


class RabbitMQEventBus(EventBus):
    """RabbitMQ implementation of the RKJO AI event bus."""

    def __init__(
        self,
        *,
        max_delivery_attempts: int = 3,
        dlq_suffix: str = ".dlq",
    ) -> None:
        if max_delivery_attempts <= 0:
            raise ValueError(
                "max_delivery_attempts must be greater than zero."
            )

        if not dlq_suffix or not dlq_suffix.strip():
            raise ValueError(
                "dlq_suffix must not be empty."
            )

        self.max_delivery_attempts = max_delivery_attempts
        self.dlq_suffix = dlq_suffix.strip()
        self.logger = get_logger("rkjo.events.rabbitmq")

        self.logger.info("Connecting to RabbitMQ...")

        parameters = pika.URLParameters(settings.rabbitmq_url)

        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()

        # Publisher confirms make a successful basic_publish synchronous with
        # the broker acknowledgement. If RabbitMQ NACKs a publication, Pika
        # raises and callers such as OutboxPublisher must not mark the message
        # as published in PostgreSQL.
        self.channel.confirm_delivery()

        self.logger.info(
            "Connected to RabbitMQ successfully with publisher confirms enabled."
        )

    def publish(self, queue_name: str, message: str) -> None:
        """Publish a persistent text message with broker confirmation."""
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
            mandatory=True,
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
        """Consume legacy text messages."""
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
        """Publish a persistent AgentMessage with broker confirmation."""
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
            mandatory=True,
        )

        self.logger.info(
            "AgentMessage '%s' confirmed by RabbitMQ on queue '%s' "
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
        """Consume AgentMessages with bounded retries and a durable DLQ."""
        self.channel.queue_declare(
            queue=queue_name,
            durable=True,
        )

        self.channel.queue_declare(
            queue=self._dlq_name(queue_name),
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

            except Exception as exc:
                self.logger.exception(
                    "Error while processing AgentMessage from queue '%s'.",
                    queue_name,
                )

                self._retry_or_dead_letter(
                    channel=channel,
                    method=method,
                    properties=properties,
                    body=body,
                    queue_name=queue_name,
                    error=exc,
                )
                return

            channel.basic_ack(
                delivery_tag=method.delivery_tag,
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

    def _retry_or_dead_letter(
        self,
        *,
        channel,
        method,
        properties,
        body: bytes,
        queue_name: str,
        error: Exception,
    ) -> None:
        """Republish a failed delivery or move it to the DLQ.

        Publisher confirms are enabled on this channel, so the original
        delivery is acknowledged only after RabbitMQ confirms the replacement
        retry/DLQ publication. A broker NACK or unroutable publication raises
        and leaves the original delivery unacknowledged for recovery.
        """
        attempt = self._delivery_attempt(properties)

        if attempt < self.max_delivery_attempts:
            next_attempt = attempt + 1
            destination = queue_name

            self.logger.warning(
                "Retrying AgentMessage from queue '%s' "
                "(attempt %d/%d).",
                queue_name,
                next_attempt,
                self.max_delivery_attempts,
            )
        else:
            next_attempt = attempt
            destination = self._dlq_name(queue_name)

            self.logger.error(
                "AgentMessage from queue '%s' exhausted %d attempts; "
                "routing to DLQ '%s'.",
                queue_name,
                attempt,
                destination,
            )

        channel.queue_declare(
            queue=destination,
            durable=True,
        )

        channel.basic_publish(
            exchange="",
            routing_key=destination,
            body=body,
            properties=self._failure_properties(
                properties=properties,
                attempt=next_attempt,
                original_queue=queue_name,
                error=error,
            ),
            mandatory=True,
        )

        channel.basic_ack(
            delivery_tag=method.delivery_tag,
        )

    @staticmethod
    def _delivery_attempt(properties) -> int:
        headers = getattr(properties, "headers", None) or {}
        raw_attempt = headers.get(_DELIVERY_ATTEMPT_HEADER, 1)

        try:
            attempt = int(raw_attempt)
        except (TypeError, ValueError):
            return 1

        return max(1, attempt)

    @staticmethod
    def _failure_properties(
        *,
        properties,
        attempt: int,
        original_queue: str,
        error: Exception,
    ) -> pika.BasicProperties:
        headers = dict(
            getattr(properties, "headers", None) or {}
        )
        headers[_DELIVERY_ATTEMPT_HEADER] = attempt
        headers[_ORIGINAL_QUEUE_HEADER] = original_queue
        headers[_FAILURE_TYPE_HEADER] = type(error).__name__
        headers[_FAILURE_MESSAGE_HEADER] = str(error)[:512]

        return pika.BasicProperties(
            content_type=(
                getattr(properties, "content_type", None)
                or "application/json"
            ),
            content_encoding=getattr(
                properties,
                "content_encoding",
                None,
            ),
            headers=headers,
            delivery_mode=(
                getattr(properties, "delivery_mode", None)
                or pika.DeliveryMode.Persistent
            ),
            priority=getattr(properties, "priority", None),
            correlation_id=getattr(
                properties,
                "correlation_id",
                None,
            ),
            reply_to=getattr(properties, "reply_to", None),
            expiration=getattr(properties, "expiration", None),
            message_id=getattr(properties, "message_id", None),
            timestamp=getattr(properties, "timestamp", None),
            type=getattr(properties, "type", None),
            user_id=getattr(properties, "user_id", None),
            app_id=getattr(properties, "app_id", None),
            cluster_id=getattr(properties, "cluster_id", None),
        )

    def _dlq_name(self, queue_name: str) -> str:
        return f"{queue_name}{self.dlq_suffix}"

    def close(self) -> None:
        """Close the RabbitMQ connection cleanly."""
        if self.connection and self.connection.is_open:
            self.connection.close()

            self.logger.info(
                "RabbitMQ connection closed successfully."
            )
