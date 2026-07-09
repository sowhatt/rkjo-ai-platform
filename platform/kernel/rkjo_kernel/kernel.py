from rkjo_kernel.config.settings import settings
from rkjo_kernel.logging.logger import get_logger
from rkjo_kernel.exceptions.base import KernelStartupError, KernelShutdownError


class RKJOKernel:
    """
    Cœur de la RKJO AI Platform.

    Pourquoi cette classe ?
    Elle centralise le démarrage, l'arrêt et l'état global du framework.
    Plus tard, tous les modules importants passeront par ce Kernel :
    - orchestrateur ;
    - agents IA ;
    - RabbitMQ ;
    - cache Redis ;
    - plugins ;
    - monitoring.
    """

    def __init__(self) -> None:
        """
        Initialise le Kernel sans encore le démarrer.

        Pourquoi ?
        On sépare la création de l'objet et le démarrage réel.
        Cela permet de tester, configurer ou injecter des dépendances avant start().
        """

        self.settings = settings
        self.logger = get_logger("rkjo.kernel")
        self.is_started = False

    def start(self) -> None:
        """
        Démarre le Kernel.

        Pourquoi ?
        Cette méthode deviendra le point d'entrée officiel de la plateforme.
        Elle initialisera progressivement :
        - la configuration ;
        - les plugins ;
        - RabbitMQ ;
        - Redis ;
        - la télémétrie ;
        - le registre des agents.
        """

        try:
            self.logger.info("Starting RKJO AI Kernel...")
            self.logger.info(f"Application: {self.settings.app_name}")
            self.logger.info(f"Environment: {self.settings.app_env}")

            self.is_started = True

            self.logger.info("RKJO AI Kernel started successfully.")

        except Exception as exc:
            raise KernelStartupError("Failed to start RKJO AI Kernel") from exc

    def stop(self) -> None:
        """
        Arrête proprement le Kernel.

        Pourquoi ?
        Une plateforme professionnelle doit libérer ses ressources correctement :
        - connexions réseau ;
        - consommateurs RabbitMQ ;
        - connexions base de données ;
        - tâches asynchrones ;
        - agents en cours.
        """

        try:
            self.logger.info("Stopping RKJO AI Kernel...")

            self.is_started = False

            self.logger.info("RKJO AI Kernel stopped successfully.")

        except Exception as exc:
            raise KernelShutdownError("Failed to stop RKJO AI Kernel") from exc

    def health(self) -> dict:
        """
        Retourne l'état du Kernel.

        Pourquoi ?
        Cette méthode servira plus tard à alimenter :
        - l'endpoint /health ;
        - Docker healthcheck ;
        - monitoring ;
        - supervision.
        """

        return {
            "app_name": self.settings.app_name,
            "environment": self.settings.app_env,
            "status": "started" if self.is_started else "stopped",
        }