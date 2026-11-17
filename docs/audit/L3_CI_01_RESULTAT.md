# L3-CI-01 — diagnostic et qualification

État : correctif backend qualifié ; livraison bloquée par npm audit (détails ci-dessous). Base ce4de07cee91c92ddbf6c9a8206b5f56ec2f3891.
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

## Qualification ciblée après correction

Campagne corrigée au SHA cfa13a0, exactement dix démarrages à froid : **10/10
réussis, zéro erreur/échec/skip**, setup/call/teardown tous réussis. Les volumes
et preuves de la campagne initiale restent conservés. Les captures Docker du
nouveau healthcheck montrent son refus pendant le démarrage puis l'ouverture
effective du listener avant admission. Ce résultat qualifie le protocole annoncé,
sans garantie universelle de stabilité ni attribution certaine de l'ancienne CI.
Les détails des vingt exécutions sont dans `L3_CI_01_EVIDENCE.json` ; le manifeste
privé donne les SHA-256 de chaque fichier brut conservé sous `.test-results/`.

Collecte/expurgation et résumé CI : huit tests ciblés réussis sans skip, dont
injection contrôlée de setup/call/teardown dans un sous-pytest pour vérifier la
conservation des exceptions complètes. Gitleaks sur les copies publiables des
vingt exécutions : zéro détection. Aucun log brut n'est ajouté au dépôt.

L3-CI-01 reste ouvert jusqu'aux contrôles complets et à la CI post-fusion verte.
L4 n'est pas commencé.

## Bilan de livraison du correctif — 17 novembre 2026

**Correctif L3-CI-01 reproduit et qualifié côté backend ; livraison BLOQUÉE
par le contrôle de sécurité web.** [PR #18](https://github.com/sowhatt/rkjo-ai-platform/pull/18)
en brouillon, non fusionnée. Candidat d2521db0bd4dbfef7fb9fa11a42b0c0e49fe9b19,
base de consolidation inchangée ce4de07cee91c92ddbf6c9a8206b5f56ec2f3891.

[CI 44142422117](https://github.com/sowhatt/rkjo-ai-platform/actions/runs/44142422117),
première tentative, checkout du merge synthétique
674561df0696465ae52654643eed0ef61ba48a3d : **8 L1, 7 L2 et 1 448 régressions
réussis, zéro échec/erreur/skip**, 55 dépendances verrouillées, packaging installé
et importé hors dépôt réussi. Les artefacts L1 contiennent 24 rapports de phase
réussis, un JUnit complet et 33 logs de processus expurgés ; Gitleaks zéro détection.
La CI a passé npm ci et lint, puis s'est arrêtée sur npm audit : build/proxy non
exécutés par cette CI. Ils ont ensuite été exécutés localement sur le même
candidat dans un conteneur Node 24.22.3 dédié, lock inchangé : npm ci, lint,
build et six routes Next réelles du test proxy réussis (upstream synthétique).

### Prérequis externe manquant : version corrigée de picomatch

L'audit web signale 14 dépendances affectées directement ou transitivement par
[GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf), sévérité
high. L'avis a été mis à jour le 17 novembre ; versions affectées <=4.0.7,
aucune version corrigée déclarée. La consultation du registre npm confirme
`latest=4.0.7` ; le lock contient 2.3.2 et 4.0.5. L'audit local indépendant du
lock reproduit le signalement. Il ne s'agit ni d'une erreur réseau ni d'un test
instable : aucune relance identique n'a été demandée.

La suggestion npm `audit fix --force` implique un changement non compatible de
configuration ESLint/Next et ne fournit pas une version corrigée de picomatch.
Elle n'est pas appliquée. Aucun seuil d'audit abaissé, exclusion des devDependencies,
suppression du contrôle ou renommage de paquet pour masquer l'avis. Remplacer
la chaîne de lint ou maintenir un fork du parseur serait un chantier supplémentaire,
hors correctif AMQP autorisé.

Déblocage attendu : publication amont d'une version corrigée compatible, ou
solution de dépendances explicitement validée dans un périmètre approprié ;
actualiser seulement le lock nécessaire, conserver les tests/audit puis obtenir
une CI complète verte avant fusion et une CI post-fusion verte. Responsable
externe de la correction : mainteneurs picomatch ; intégration à affecter au socle.
Le présent correctif reste prêt pour cette requalification, sans contournement.

L'ancienne CI 44116538750, ses preuves et les vingt résultats avant/après sont
conservés. La reproduction établit la cause AMQP, mais ne restaure pas l'exception
historique perdue : cette limite demeure explicite. Aucun nouvel appel Ollama,
aucune revendication de qualité générale RAG. Les sept clôtures fonctionnelles
L3 restent distinctes de l'acceptation de livraison bloquée.

**Pas de fusion PR #18, donc pas de CI post-fusion du correctif. L4 — outils
sensibles et transports MCP n'est pas commencé.** Aucun autre lot, aucune fusion
vers main ni déploiement. WIP d'origine et branche candidate préservés.
