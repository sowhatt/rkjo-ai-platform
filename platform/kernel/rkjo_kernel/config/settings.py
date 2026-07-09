from pydantic_settings import BaseSettings, SettingsConfigDict


class KernelSettings(BaseSettings):
    """
    Configuration centrale du RKJO AI Kernel.

    Pourquoi cette classe ?
    Elle centralise les paramètres techniques de toute la plateforme :
    environnement, logs, RabbitMQ, Redis et PostgreSQL.

    Les valeurs peuvent être remplacées automatiquement par des variables
    d'environnement ou par un fichier .env.
    """

    # Identité de la plateforme
    app_name: str = "RKJO AI Platform"

    # Environnement courant : local, development, staging ou production
    app_env: str = "local"

    # Active les fonctionnalités utiles au développement.
    # En production, cette valeur devra être False.
    debug: bool = True

    # Niveau minimal des logs affichés.
    log_level: str = "INFO"

    # Adresse du broker RabbitMQ.
    # RabbitMQ assurera notamment le transport fiable des tâches entre agents.
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"

    # Adresse de Redis.
    # Redis servira notamment au cache et aux états temporaires.
    redis_url: str = "redis://localhost:6379/0"

    # Adresse de PostgreSQL.
    # Plus tard, PostgreSQL accueillera également PostGIS et pgvector.
    database_url: str = (
        "postgresql://rkjo:rkjo@localhost:5432/rkjo_ai"
    )

    # Configuration moderne compatible avec Pydantic v2.
    #
    # Pourquoi ?
    # L'ancienne syntaxe "class Config" est dépréciée.
    # Cette configuration demande à Pydantic de lire automatiquement le fichier
    # .env et d'ignorer les variables supplémentaires qu'il ne connaît pas encore.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Instance globale de configuration.
# Tous les composants du Kernel peuvent importer cette même instance.
settings = KernelSettings()