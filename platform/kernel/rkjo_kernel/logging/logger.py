import logging

# On importe la configuration globale du Kernel.
# Exemple : niveau de log INFO, DEBUG, ERROR...
from rkjo_kernel.config.settings import settings


def get_logger(name: str) -> logging.Logger:
    """
    Crée et retourne un logger standardisé pour toute la plateforme RKJO.

    Pourquoi ?
    - Avoir le même format de logs partout.
    - Éviter que chaque module configure ses logs différemment.
    - Faciliter le debug et l'observabilité plus tard.
    """

    # On récupère ou crée un logger Python avec le nom du module appelant.
    logger = logging.getLogger(name)

    # Si le logger a déjà des handlers, on le retourne directement.
    # Pourquoi ?
    # Pour éviter de dupliquer les logs à chaque import.
    if logger.handlers:
        return logger

    # On définit le niveau de log depuis settings.py.
    # Exemple : INFO en production, DEBUG en développement.
    logger.setLevel(settings.log_level)

    # StreamHandler affiche les logs dans le terminal.
    # Plus tard, on pourra ajouter des handlers vers fichier, Grafana, Datadog, etc.
    handler = logging.StreamHandler()

    # Format standard des logs.
    # Exemple :
    # 2026-07-09 15:20:00 | INFO | rkjo_kernel | Kernel started
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    # On attache le format au handler.
    handler.setFormatter(formatter)

    # On attache le handler au logger.
    logger.addHandler(handler)

    # On empêche la propagation pour éviter les doublons.
    logger.propagate = False

    return logger