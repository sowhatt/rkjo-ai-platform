from time import perf_counter
from typing import Any

from rkjo_kernel.agents.base_agent import BaseAgent
from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.logging.logger import get_logger
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.registry.descriptor import AgentStatus
from rkjo_kernel.runtime.dead_letter_publisher import DeadLetterPublisher
from rkjo_kernel.runtime.result_publisher import AgentResultPublisher
from rkjo_kernel.runtime.retry_message import build_retry_message
from rkjo_kernel.runtime.retry_policy import RetryPolicy
from rkjo_kernel.runtime.status import RuntimeStatus
from rkjo_kernel.services.registry_service import RegistryService


class AgentRuntime:
    """
    Environnement d'exécution d'un agent RKJO.

    Pourquoi cette classe ?

    BaseAgent contient la logique commune de traitement.

    AgentRuntime prend en charge la vie technique de l'agent :

    - démarrage ;
    - consommation des messages ;
    - arrêt ;
    - changement de statut ;
    - mesure des traitements ;
    - gestion des erreurs ;
    - exposition de l'état de santé.

    Le Runtime dépend de l'interface EventBus,
    mais ne connaît pas RabbitMQ directement.
    """

    def __init__(
        self,
        agent: BaseAgent,
        event_bus: EventBus,
        registry_service: RegistryService,
        result_publisher: AgentResultPublisher | None = None,
        retry_policy: RetryPolicy | None = None,
        dead_letter_publisher: DeadLetterPublisher | None = None,
    ) -> None:
        """
        Initialise le Runtime sans le démarrer.

        Les dépendances sont injectées afin de faciliter :
        - les tests unitaires ;
        - le changement de technologie de messagerie ;
        - le remplacement du Registry ;
        - l'isolation des responsabilités.
        """

        self.agent = agent
        self.event_bus = event_bus
        self.registry_service = registry_service
        self.result_publisher = result_publisher
        self.retry_policy = retry_policy
        self.dead_letter_publisher = dead_letter_publisher

        self.status = RuntimeStatus.CREATED
        self.last_error: str | None = None
        self.last_duration_ms: float | None = None
        self.total_runtime_messages = 0

        self.logger = get_logger(
            f"rkjo.runtime.{self.agent.agent_name}"
        )

    def start(self) -> None:
        """
        Démarre l'écoute de la file associée à l'agent.

        Avec RabbitMQEventBus, cette méthode est actuellement bloquante :
        elle reste active tant que le consommateur écoute la file.

        Plus tard, les Runtime pourront être exécutés dans :
        - des processus séparés ;
        - des conteneurs ;
        - des workers Kubernetes.
        """

        if self.status in {
            RuntimeStatus.STARTING,
            RuntimeStatus.RUNNING,
        }:
            self.logger.warning(
                "Runtime for agent '%s' is already active.",
                self.agent.agent_name,
            )
            return

        self.logger.info(
            "Starting runtime for agent '%s'...",
            self.agent.agent_name,
        )

        self.status = RuntimeStatus.STARTING
        self.last_error = None

        try:
            self.registry_service.update_agent_status(
                agent_name=self.agent.agent_name,
                status=AgentStatus.AVAILABLE,
            )

            self.status = RuntimeStatus.RUNNING

            self.event_bus.consume_agent_messages(
                queue_name=self.agent.queue_name,
                callback=self._consume_message,
            )

        except Exception as exc:
            self.status = RuntimeStatus.ERROR
            self.last_error = str(exc)

            self._mark_agent_error()

            self.logger.exception(
                "Runtime for agent '%s' failed.",
                self.agent.agent_name,
            )

            raise

        finally:
            # Si la consommation se termine normalement,
            # le Runtime ne doit pas rester marqué comme actif.
            if self.status != RuntimeStatus.ERROR:
                self.status = RuntimeStatus.STOPPED
                self._mark_agent_stopped()

    def stop(self) -> None:
        """
        Arrête le Runtime et ferme le bus.

        Dans une version future, EventBus disposera d'une méthode dédiée
        permettant d'arrêter seulement un consommateur sans fermer
        toute la connexion.
        """

        if self.status == RuntimeStatus.STOPPED:
            return

        self.logger.info(
            "Stopping runtime for agent '%s'...",
            self.agent.agent_name,
        )

        self.status = RuntimeStatus.STOPPING

        self.event_bus.close()

        self.status = RuntimeStatus.STOPPED
        self._mark_agent_stopped()

        self.logger.info(
            "Runtime for agent '%s' stopped.",
            self.agent.agent_name,
        )


    def execute(
        self,
        message: AgentMessage,
    ) -> Any:
        """Execute one message synchronously.

        This public method is used by local execution adapters.
        Message lifecycle, metrics and registry status changes remain
        centralized in the internal runtime pipeline.
        """
        return self._handle_message(message)

    def _consume_message(
        self,
        message: AgentMessage,
    ) -> Any:
        """Consume one broker message with controlled retry/DLQ.

        execute() keeps synchronous semantics and raises failures.

        This consumer boundary converts failures already classified by
        RetryPolicy into explicit retry or dead-letter messages. Once
        routing succeeds, the exception is intentionally not propagated,
        allowing EventBus to ACK the original physical message.
        """

        try:
            return self.execute(message)

        except Exception:
            if self.retry_policy is None:
                raise

            should_retry = bool(
                message.metadata.get(
                    "retry_should_retry",
                    False,
                )
            )

            if should_retry:
                retry_message = build_retry_message(
                    original_message=message
                )

                self.event_bus.publish_agent_message(
                    queue_name=self.agent.queue_name,
                    message=retry_message,
                )

                self.logger.warning(
                    "Retrying message '%s' as '%s' "
                    "for agent '%s' (attempt %s).",
                    message.message_id,
                    retry_message.message_id,
                    self.agent.agent_name,
                    retry_message.metadata.get(
                        "attempt"
                    ),
                )

                return None

            if self.dead_letter_publisher is None:
                raise

            reason = str(
                message.metadata.get(
                    "retry_reason",
                    "agent_execution_failed",
                )
            )

            self.dead_letter_publisher.publish(
                original_message=message,
                reason=reason,
            )

            self.logger.error(
                "Message '%s' moved to DLQ "
                "after terminal agent failure.",
                message.message_id,
            )

            return None

    def _handle_message(
        self,
        message: AgentMessage,
    ) -> Any:
        """
        Encadre le traitement d'un message par l'agent.

        Le Runtime mesure la durée et synchronise le statut public
        de l'agent avec le RegistryService.
        """

        # Une erreur précédente ne doit pas empêcher
        # un traitement réussi de remettre l'agent
        # en état AVAILABLE.
        self.last_error = None

        started_at = perf_counter()

        self.registry_service.update_agent_status(
            agent_name=self.agent.agent_name,
            status=AgentStatus.BUSY,
        )

        try:
            result = self.agent._handle_message(message)

            self.total_runtime_messages += 1

            if self.result_publisher is not None:
                self.result_publisher.publish_success(
                    request=message,
                    result=result,
                )

            return result

        except Exception as exc:
            self.last_error = str(exc)
            self._mark_agent_error()

            if self.retry_policy is not None:
                attempt = int(
                    message.metadata.get(
                        "attempt",
                        1,
                    )
                )

                decision = self.retry_policy.decide(
                    error=exc,
                    attempt=attempt,
                )

                message.metadata[
                    "retry_should_retry"
                ] = decision.should_retry

                message.metadata[
                    "retry_attempt"
                ] = decision.attempt

                message.metadata[
                    "retry_max_attempts"
                ] = decision.max_attempts

                message.metadata[
                    "retry_delay_seconds"
                ] = decision.delay_seconds

                message.metadata[
                    "retry_reason"
                ] = decision.reason

            should_retry = bool(
                message.metadata.get(
                    "retry_should_retry",
                    False,
                )
            )

            if (
                self.result_publisher is not None
                and not should_retry
            ):
                self.result_publisher.publish_failure(
                    request=message,
                    error=exc,
                )

            raise

        finally:
            elapsed_seconds = perf_counter() - started_at
            self.last_duration_ms = elapsed_seconds * 1000

            # Si aucune erreur n'est active, l'agent redevient disponible.
            if self.last_error is None:
                self.registry_service.update_agent_status(
                    agent_name=self.agent.agent_name,
                    status=AgentStatus.AVAILABLE,
                )

    def _mark_agent_error(self) -> None:
        """
        Marque l'agent en erreur dans le Registry lorsque cela est possible.
        """

        try:
            self.registry_service.update_agent_status(
                agent_name=self.agent.agent_name,
                status=AgentStatus.ERROR,
            )
        except KeyError:
            self.logger.warning(
                "Unable to mark unknown agent '%s' as error.",
                self.agent.agent_name,
            )

    def _mark_agent_stopped(self) -> None:
        """
        Marque l'agent comme arrêté dans le Registry.
        """

        try:
            self.registry_service.update_agent_status(
                agent_name=self.agent.agent_name,
                status=AgentStatus.STOPPED,
            )
        except KeyError:
            self.logger.warning(
                "Unable to mark unknown agent '%s' as stopped.",
                self.agent.agent_name,
            )

    def health(self) -> dict[str, Any]:
        """
        Retourne l'état technique du Runtime.

        Ces informations serviront ensuite au Health Manager,
        à Prometheus et au tableau de supervision.
        """

        return {
            "agent_name": self.agent.agent_name,
            "queue_name": self.agent.queue_name,
            "runtime_status": self.status.value,
            "total_runtime_messages": self.total_runtime_messages,
            "last_duration_ms": self.last_duration_ms,
            "last_error": self.last_error,
            "agent_health": self.agent.health(),
        }