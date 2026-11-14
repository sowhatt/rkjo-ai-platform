# L1 — workflow neutre durable, configuration et recette

Périmètre : `AGT-03`, `MIS-02`, `WF-04`, `WF-07`, `SEC-03` du plan de clôture.
Base : consolidation `377e0d02221927ac14ebfad48e85a8a873d17210`.
Aucun LLM, domaine métier, navigateur ou fournisseur externe nécessaire.

## Contrat livré

L'API crée l'exécution insert-only avec tenant, principal, rôle, mission, trace
et requête issus de l'identité/du serveur. Les champs d'autorité fournis dans
les métadonnées globales ou d'étape sont refusés (403) ; les champs JSON inconnus
au niveau requête/étape sont refusés (422). Un tenant explicitement fourni et
identique au tenant authentifié reste compatible. Une clé API est un principal
technique `api-key:<empreinte>`, uniquement pour les workflows ; elle ne devient
pas un utilisateur des autres domaines. Les données `input_data` restent des
données, jamais une source d'autorité.

Le premier start verrouille la ligne d'exécution et applique le contrôle tenant
dans cette transaction. État RUNNING et intention outbox sont commis ensemble.
Le second start concurrent reçoit 409 ; route absente ou erreur PostgreSQL donne
503 avec rollback. L'API ne se connecte pas au broker pour préparer ce start.
Le dispatch par capacité conserve la capacité et cible le nom de l'agent résolu.

API, worker et résultat utilisent `PostgresAgentRegistry`. L'instance s'enregistre
au démarrage du runtime, renouvelle un bail, et ne peut modifier le statut d'une
instance qui l'a remplacée. Après SIGKILL, découverte indisponible au plus tard à
l'expiration du bail (30 s par défaut). Une panne immédiatement après découverte
peut laisser un message en attente, mais son intention durable reste récupérable.
Le bootstrap du registre est sérialisé pour des démarrages simultanés.

Avant tout appel agent, la requête broker doit être identique à l'intention
outbox persistée : ID, payload, cible, source, contexte, étape et file de retour.
Le worker vérifie également l'état et le propriétaire persistés, sous verrou.
Un ancien message authentique d'une étape achevée est acquitté sans nouvel appel.
Un message falsifié ne publie pas de faux résultat d'échec. Les retries du profil
livré sont ceux du transport RabbitMQ (même enveloppe, trois tentatives, puis DLQ).
Les retries applicatifs créant de nouveaux IDs ne sont pas activés sur ce profil.

Le résultat complet est signé HMAC-SHA256 par le worker. Le consumer vérifie
signature, source/cible, corrélation, requête d'origine, tenant, principal et
étape **avant** l'inbox. Un faux message réutilisant un ID légitime ne peut donc
pas empoisonner la déduplication. Résultat, inbox et intention suivante partagent
la transaction existante. Une panne de publication du résultat réussi ne devient
plus un faux résultat métier d'échec.

La base et la clé HMAC appartiennent aux services de confiance. La clé du profil
ne doit être accessible qu'au worker neutre et au consumer de résultats. Elle
n'est ni une donnée de message ni un credential client. Ce profil qualifie un
worker générique ; la délégation entre services mutuellement non fiables demande
des credentials distincts et une politique dédiée. Pas de promesse d'effet
externe exactement une fois. Révocation dynamique, RLS, production et L2 restent
hors périmètre.

Les deux copies de métadonnées d'autorité existantes sont conservées et doivent
concorder. Les anciennes exécutions sans contexte canonique complet ne démarrent
pas (404) ; aucune adoption automatique depuis un message ou un nouvel appelant.
Toute migration doit obtenir l'identité d'une source de confiance. Les intentions
outbox publiées restent nécessaires à l'autorisation et aux replays : ne pas les
purger tant que l'exécution et sa fenêtre de reprise sont conservées.

## Provenance et adaptations

| Source existante | Reprise L1 |
| --- | --- |
| `df46bf2` | Registre PostgreSQL partagé et factories |
| `a117602`, `6085120` | Garde par instance, enregistrement au start, tests rotation |
| `a8c8e8e`, `80556e3` | Publisher worker et registre du consumer |
| `c59b87c`, `a33a4e5`, `b947a11` | Factory UoW, premier dispatch transactionnel, cible résolue |
| S1 `55681df`/`ada39d0` | Principe de comparaison à l'autorité persistée ; adaptation aux deux metadata A, capacité seule et reply_queue canonique non nul |

Aucun fichier d'endpoint métier repris. Les patches Runtime ont été adaptés pour
conserver `context_runtime`. Le contrôle tenant de la consolidation reste dans
le start transactionnel. Ajouts nécessaires : expiration d'instance, admission
contre outbox, signature de résultat, refus des autorités HTTP, priorité du
contexte canonique à la frontière outil, configuration et recette.

## Reproduction sur services exclusivement dédiés

Prérequis : Docker/Compose, Python 3.12 avec les dépendances de test, Poppler et
Tesseract pour la suite complète. Le manifeste de l'environnement réellement
utilisé est livré avec les preuves. Le runner refuse un projet sans préfixe
`rkjo-l1-` ou une copie contenant `.env`, vérifie la santé et l'identité Compose,
utilise les ports localhost attribués et écrase les DSN hérités.

Depuis la copie isolée, sans autre campagne simultanée dans ce projet :

```bash
docker compose -p rkjo-l1-20261114 -f compose.l1.yml up -d --wait
/Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python scripts/l1_test.py --project rkjo-l1-20261114 tests/l1 -q --junitxml=.test-results/l1/acceptance.xml
/Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python scripts/l1_test.py --project rkjo-l1-20261114 tests -q --junitxml=.test-results/l1/full-suite.xml
```

Ces commandes utilisent le venv existant en lecture seule. Sur une autre machine,
créer son propre venv et installer les versions de `environment-freeze.txt` des
preuves, ou qualifier séparément `requirements-test-lock.txt` ; remplacer ensuite
le chemin Python dans les deux commandes. Aucune installation de dépendances ne
doit modifier un environnement partagé.

Le runner lance, sans remplacer leurs factories, les commandes suivantes en
enfants indépendants avec DSN dédiés et clés de test :

```bash
python -m uvicorn rkjo_api.main:app --host 127.0.0.1 --port PORT_LIBRE
python -m rkjo_worker.main
python -m rkjo_worker.workflow_result_consumer
python -m rkjo_worker.outbox_worker
```

La migration est la vraie `PostgreSQLWorkflowUnitOfWork.initialize_schema()`.
Pour un lancement manuel, la commande équivalente est :

```bash
python -m rkjo_kernel.workflow.schema_bootstrap
```

`PYTHONPATH` doit inclure `platform/kernel:platform/api:platform/worker:domains/education:.`
pour les imports actuels de l'API ; aucun parcours Éducation n'est requis par L1.
`DATABASE_URL` et `RKJO_DATABASE_URL` doivent désigner la même base dédiée.

| Variable | Contrat |
| --- | --- |
| `RKJO_DATABASE_URL`, `DATABASE_URL` | DSN PostgreSQL dédié ; obligatoire pour la recette |
| `RABBITMQ_URL` | Broker dédié ; le runner configure aussi `RKJO_TEST_RABBITMQ_URL` |
| `RKJO_JWT_SECRET` | Clé JWT locale de test, distincte de la clé résultat |
| `RKJO_API_KEY` | Configuration d'authentification API, même pour tester les refus anonymes |
| `RKJO_WORKFLOW_RESULT_SECRET` | Au moins 32 octets ; requis dans worker et résultat ; absent → refus de bootstrap sécurisé |
| `RKJO_WORKFLOW_RESULT_QUEUE` | Même valeur API/worker/consumer ; défaut `rkjo.workflow.results` |
| `RKJO_WORKER_LEASE_SECONDS` | Positif ; défaut 30, recette 3 ; renouvellement à bail/3 |
| `RKJO_WORKER_HEALTH_HOST/PORT` | Interface et port libres ; recette localhost |
| `RKJO_OUTBOX_POLL_INTERVAL_SECONDS` | Défaut 1 s, recette 0,05 s |

Le Compose applicatif contient désormais les quatre services. Sa syntaxe est
vérifiée ; la preuve d'exécution L1 est celle des commandes natives ci-dessus,
pas une qualification de construction/déploiement des images applicatives.

## Scénarios et preuves

`tests/l1/test_acceptance.py` contient sept scénarios réels :

1. Deux étapes capacité puis nom, passage des sorties, relecture après redémarrage
   des quatre processus et refus de recréation insert-only.
2. Deux starts sous barrière : 202/409, une intention ; SIGKILL API après commit
   avant publisher, reprise puis deux sorties.
3. SIGKILL worker, expiration réelle du bail, 503/PENDING ; trigger PostgreSQL
   d'échec après INSERT outbox, rollback intégral ; retrait du trigger et succès.
4. Refus HTTP anonyme/viewer/intertenant/non lié, champs forgés globalement/dans
   l'étape, legacy sans propriétaire, sans mutation ni intention.
5. Requêtes broker falsifiées et résultats signés incohérents ou non signés : DLQ
   réelle, zéro progression, puis traitement du message légitime portant le même ID.
6. Pause du consumer après commit mais avant ACK, SIGKILL, redelivery réelle,
   une seule continuation ; replay d'une ancienne requête sans nouvel effet.
7. Échec SQL transitoire avant inbox par trigger à séquence non rollbackée :
   tentative broker 2/3 observée, puis COMPLETED, sans DLQ.

Le seul instrument du scénario 6 est `tests/l1/process_fault.py`, qui suspend
`BlockingChannel.basic_ack` dans le vrai consumer. Il ne remplace ni handler,
ni factory, ni base, ni broker. Les autres pannes utilisent SIGKILL ou SQL réel.
Un huitième test bibliothèque vérifie la priorité de l'identité canonique vers
l'outil local ; ce test n'est pas présenté comme un appel outil distribué.

Conserver `.test-results/l1/` : JUnit, manifeste d'infrastructure, versions Python,
chronologies HTTP et PID/commandes, sorties SQL, logs des quatre processus. Aucun
JWT ni secret de connexion n'est écrit dans les chronologies. Les scénarios sont
sériels et utilisent des triggers globaux **dans la seule base de test dédiée**.

Après conservation des preuves, arrêter uniquement le projet de recette :

```bash
docker compose -p rkjo-l1-20261114 -f compose.l1.yml stop
```

Cette commande conserve les volumes. Ne pas arrêter ou nettoyer d'autres projets.
