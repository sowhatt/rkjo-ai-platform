# L3-CI-01 — diagnostic et qualification

État : correctif en qualification. Base ce4de07cee91c92ddbf6c9a8206b5f56ec2f3891.
Protocole initial commité avant exécution : d5cf335a178f46871b4b4a3ec35975ab2c3dc4fb,
SHA-256 du protocole 8e765d1d696f4bf88e364ce7f72b4ccdf5038bf33e8b878a7018925380815660.

## Diagnostic certain

Dix répétitions indépendantes sur volumes neufs, dépendances verrouillées :
**1 réussite (n°1), 9 erreurs (n°2 à 10), zéro skip**. Toutes sont conservées,
sans relance. Le hook pytest et les processus établissent une erreur de setup :
`stack → start(worker) → RabbitMQEventBus → pika.BlockingConnection` ; le worker
sort avant readiness avec `IncompatibleProtocolError: StreamLostError: Transport
indicated EOF`. Il n'atteint ni le registre ni le workflow.

Exemple n°2 : tentative du worker à 17:42:44.938 UTC ; le journal broker ouvre
le listener 5672 à 17:42:45.187 UTC, après le lancement du test autorisé par
Compose. La table agent_registry n'existe pas lors de la capture ; aucune étape
workflow n'a été dispatchée. Le healthcheck existant vérifiait seulement `ping`.
[RabbitMQ documente](https://www.rabbitmq.com/docs/monitoring) que ce contrôle
vérifie le runtime et non la disponibilité des connexions client ; le
[contrôle du listener](https://www.rabbitmq.com/docs/man/rabbitmq-diagnostics.8)
vérifie explicitement le port demandé.

Cause démontrée de la reproduction : admission prématurée de l'infrastructure
de test, pas une panne de découverte, de mémoire ou de génération L3.
Pour la CI historique 44116538750, l'exception n'est plus disponible : la
correspondance de symptôme/position ne prouve pas rétroactivement sa cause.
L'ancien HTTP 503 de la recette Ollama reste un autre incident non attribué.
Aucune hypothèse d'horloge n'est nécessaire à ce correctif.

## Correctif minimal

`compose.l1.yml` et le service RabbitMQ de la CI de régression exigent désormais
`rabbitmq-diagnostics -q check_port_listener 5672`. Intervalles, délais, nombre
de tentatives de healthcheck et assertions de test inchangés. Aucun retry du
workflow ou worker ajouté, aucune modification de runtime applicatif.
La campagne corrigée prévue au protocole comporte exactement dix volumes neufs.

Le lanceur conserve JUnit complet, stdout, exceptions setup/call/teardown,
logs API/worker/results/outbox, snapshots registre/SQL/readiness avant nettoyage,
horodatages UTC/monotones et diagnostics broker/healthchecks. La CI ne publie que
les copies expurgées ; les bruts restent locaux/éphémères, jamais ajoutés à Git.
Les diagnostics n'appellent pas `/ready` API (qui modifie le schéma) et ne
consomment aucun message. Le test du collecteur provoque volontairement trois
erreurs dans un sous-pytest et vérifie leur capture, sans ignorer un test réel.

## Commandes reproductibles

Dans une copie isolée sans `.env`, Python 3.12 et venv installé avec
`python -m pip install -r requirements-test-lock.txt` :

```sh
python scripts/l3_ci_01_campaign.py --campaign initial --tag UNIQUEINITIAL
python scripts/l3_ci_01_campaign.py --campaign corrected --tag UNIQUECORRECTED
```

La première commande doit être lancée au commit d5cf335 pour reproduire l'ancien
healthcheck, la seconde au correctif. Les tags sont uniques et alphanumériques ;
le script refuse tout réemploi de répertoire/projet. Il conserve les dix résultats
et arrête seulement ses projets dédiés, sans supprimer leurs volumes. Les
commandes de qualification complète sont celles du workflow de consolidation.

L3-CI-01 reste ouvert jusqu'aux contrôles complets et à la CI post-fusion verte.
L4 n'est pas commencé.
