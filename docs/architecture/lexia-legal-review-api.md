# LexIA — API de revue juridique sécurisée (phase 1)

Routes protégées :
- GET /rag/lexia/review/{packet_id}/events : journal de revue.
- POST /rag/lexia/review/{packet_id}/events : ajouter une action review_requested, review_note ou rejected.

L'API exige un JWT ou une identité middleware avec un sujet individuel non vide, un tenant authentifié et le rôle operator ou admin. Les clés API sans sujet individuel ne peuvent pas réaliser une décision de juriste. Le corps JSON n'accepte ni tenant_id ni actor_id : ceux-ci sont dérivés de l'identité, pas des données client.

L'accès à un packet absent ou à celui d'un autre cabinet donne 404, sans divulgation de détails. Le dépôt PostgreSQL n'accepte ni approved ni published et aucune route de publication n'existe dans cette phase.

Préparation de schéma : créer les tables de revue avec PostgresLegalReviewInbox.initialize_schema() dans une migration administrée, avant de servir les endpoints. L'API n'initialise jamais elle-même les tables dans chaque requête.

Contrôles restants avant production :
- Revue de l'authentification JWT et du mappage d'identité des juristes habilités dans LexIA ; operator/admin RKJO ne suffit pas à prouver la qualité de juriste ni les droits sur un dossier spécifique.
- Journal PostgreSQL append-only actuellement au niveau applicatif seulement ; le rôle DB utilisé par l'API ne doit pas avoir UPDATE/DELETE sur la table des événements, et une politique de rétention doit être définie.
- Fichier source non stocké dans cet inbox ; sécurisation et conservation des originaux, validation de la source institutionnelle, procédure de publication à quatre yeux à développer séparément.
- Aucun endpoint d'upload ni de publication automatique n'est ajouté.

Tests : tests/api/test_lexia_review_api.py couvre identité JWT, RBAC, refus des clés anonymes, interdiction de la publication et cloisonnement tenant. tests/api/test_lexia_review_inbox_pg_e2e.py couvre la persistance sur PostgreSQL de test.
