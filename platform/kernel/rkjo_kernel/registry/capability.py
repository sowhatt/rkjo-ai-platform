from typing import Any

from pydantic import BaseModel, Field, field_validator


class AgentCapability(BaseModel):
    """
    Décrit une compétence proposée par un agent.

    Pourquoi cette classe ?

    L'orchestrateur ne doit pas sélectionner un agent uniquement par son nom.

    Il doit pouvoir demander :

        "Quel agent sait analyser la sécheresse ?"

    Le Registry cherchera alors une capacité nommée :

        drought_analysis

    Cette classe constitue donc le contrat commun utilisé pour décrire
    les compétences de tous les agents RKJO.
    """

    # Identifiant technique unique de la capacité.
    #
    # Exemples :
    # - drought_analysis
    # - weather_analysis
    # - soil_analysis
    # - scientific_search
    name: str

    # Description lisible de la compétence.
    description: str

    # Version de la capacité.
    #
    # Pourquoi ?
    # Une capacité peut évoluer indépendamment de l'agent.
    version: str = "1.0.0"

    # Données attendues en entrée.
    #
    # Exemple :
    # {
    #     "department_code": "str",
    #     "crop": "str"
    # }
    input_schema: dict[str, Any] = Field(default_factory=dict)

    # Données produites en sortie.
    #
    # Exemple :
    # {
    #     "risk_score": "float",
    #     "recommendations": "list[str]"
    # }
    output_schema: dict[str, Any] = Field(default_factory=dict)

    # Tags facilitant la recherche et le classement.
    #
    # Exemple :
    # ["climate", "agriculture", "france"]
    tags: list[str] = Field(default_factory=list)

    # Niveau de confiance annoncé par l'agent.
    #
    # 0.0 = aucune confiance
    # 1.0 = confiance maximale
    confidence_score: float = 1.0

    # Coût relatif estimé d'exécution.
    #
    # Il ne s'agit pas nécessairement d'euros.
    # Ce score permettra plus tard à l'orchestrateur de comparer
    # plusieurs agents proposant la même capacité.
    estimated_cost: float = 0.0

    # Durée moyenne estimée du traitement en millisecondes.
    average_duration_ms: int = 0

    # Indique si la capacité accepte une réponse en streaming.
    supports_streaming: bool = False

    # Indique si la capacité peut fonctionner avec un modèle local.
    supports_local_model: bool = False

    # Métadonnées libres pour les besoins futurs.
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """
        Vérifie que le nom technique est exploitable.

        Pourquoi ?

        Les capacités seront utilisées dans :
        - les recherches ;
        - les logs ;
        - les routes d'orchestration ;
        - les métriques ;
        - les API.

        Nous imposons donc un format simple en minuscules.
        """

        normalized_value = value.strip().lower()

        if not normalized_value:
            raise ValueError(
                "Capability name cannot be empty."
            )

        if " " in normalized_value:
            raise ValueError(
                "Capability name must not contain spaces. "
                "Use underscores instead."
            )

        return normalized_value

    @field_validator("confidence_score")
    @classmethod
    def validate_confidence_score(
        cls,
        value: float,
    ) -> float:
        """
        Garantit que le score de confiance reste compris entre 0 et 1.
        """

        if not 0.0 <= value <= 1.0:
            raise ValueError(
                "confidence_score must be between 0.0 and 1.0."
            )

        return value

    @field_validator("estimated_cost")
    @classmethod
    def validate_estimated_cost(
        cls,
        value: float,
    ) -> float:
        """
        Empêche la déclaration d'un coût négatif.
        """

        if value < 0:
            raise ValueError(
                "estimated_cost cannot be negative."
            )

        return value

    @field_validator("average_duration_ms")
    @classmethod
    def validate_average_duration(
        cls,
        value: int,
    ) -> int:
        """
        Empêche la déclaration d'une durée négative.
        """

        if value < 0:
            raise ValueError(
                "average_duration_ms cannot be negative."
            )

        return value