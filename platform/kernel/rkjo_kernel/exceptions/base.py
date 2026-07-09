class RKJOKernelError(Exception):
    """
    Exception de base du RKJO AI Kernel.

    Pourquoi ?
    Toutes les erreurs propres au Kernel hériteront de cette classe.
    Cela permettra de distinguer :
    - une erreur système Python classique ;
    - une erreur métier ou technique venant du Kernel.
    """


class KernelStartupError(RKJOKernelError):
    """
    Erreur déclenchée si le Kernel ne démarre pas correctement.

    Exemples :
    - configuration manquante ;
    - plugin impossible à charger ;
    - connexion RabbitMQ indisponible ;
    - initialisation du registre impossible.
    """


class KernelShutdownError(RKJOKernelError):
    """
    Erreur déclenchée si le Kernel ne s'arrête pas correctement.

    Exemples :
    - fermeture incorrecte d'une connexion ;
    - agent encore actif ;
    - événement non terminé ;
    - ressource non libérée.
    """