# L3-CI-01 — protocole fixé avant reproduction

Base distante vérifiée le 17 novembre 2026 : ce4de07cee91c92ddbf6c9a8206b5f56ec2f3891.
Première CI 44116538750 conservée dans la copie L3 précédente, jamais relancée.
Sa phase exacte et sa cause ne sont pas connues : le résumé seul indique error.

## Campagne initiale

Exécuter exactement 10 fois `tests/l1/test_acceptance.py::test_two_steps_restart_and_insert_only`,
chaque fois avec un projet Compose et des volumes neufs, PostgreSQL/RabbitMQ dédiés,
Python 3.12 et les 55 dépendances de requirements-test-lock.txt. Vrais processus
API/worker/results/outbox et factories livrés. Aucun override, retry, skip,
assertion supprimée ou délai augmenté. Conserver chaque résultat, y compris
réussite, exception complète et phase pytest, JUnit, stdout, logs processus,
registre/readiness/SQL/broker avec horodatages avant arrêt des services.
Le protocole ne modifie initialement que la collecte des preuves, pas les
healthchecks ni le runtime. Les dix résultats sont conservés même en cas d'échec.

Réussite d'une répétition : exactement un test exécuté, passé sans erreur ni skip,
deux étapes et deux intentions outbox, résultat durable identique après restart,
refus de réinsertion et identités inchangées (assertions existantes intégrales).
Une collecte incomplète est signalée ; elle ne transforme pas un échec en succès.

Après campagne : si cause démontrée, correctif minimal puis exactement dix
répétitions à froid supplémentaires sur ce correctif. Sinon ne pas inventer de
cause : rapporter 0/10 ou N/10, environnement, limites d'échantillonnage et
hypothèses. Une campagne sans échec qualifie ce protocole seulement, pas une
preuve d'absence d'instabilité (0/10 : borne supérieure unilatérale 95 % ~26 %).
Toute nouvelle campagne nécessite un changement ou une hypothèse testable
documenté ; aucune série de relances jusqu'au vert.

## Contrôles finaux

Tests de collecte/expurgation, L1 (8), L2 (7 avec IdP réel), régressions complètes,
packaging et web, dépendances verrouillées. PR limitée au blocage ; vérifier le
HEAD et le merge synthétique CI, revues et protections avant fusion autorisée.
Une première CI post-fusion complète verte ferme le blocage. Si elle échoue,
conserver les nouveaux diagnostics et investiguer avant toute relance.
L4 reste interdit tant que ce préalable manque.

## Publication

Bruts locaux privés dans `.test-results/` puis archivés hors index Git. CI publie
uniquement copies expurgées (secrets d'environnement/recette, credentials d'URL,
JWT et champs d'autorisation masqués). Aucun dump d'environnement ni message
broker consommé par les diagnostics. Les tables sont observées sans écrire.
