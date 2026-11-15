# L2 — frontières d’autorisation restantes

Base validée : `3f5ae0d2bd67b2316c642562d16f766997cfb62e`, fusion de L1 PR #15.
Périmètre exclusif : SEC-02, SEC-04, SEC-05 du plan de clôture V2-C1.
L1 est conservé et ses huit tests restent obligatoires, sans skip.

## Contrat et provenance

- **SEC-02** : POST/PUT/DELETE documentaires refusent une identité sans tenant,
  avant construction des dépendances et dépôt temporaire. Les helpers refusent
  également un tenant fourni par le client qui contredit l'identité. Les anciennes
  données sans propriétaire ne sont pas adoptées : aucune migration automatique
  depuis une requête ou un token. Ingestion, recherche et versioning existants ne
  sont pas réécrits. Les contenus de recette sont synthétiques et distincts pour
  ne pas confondre autorisation et déduplication documentaire.
- **SEC-04** : extraction limitée des primitives génériques S1 `ada39d0` :
  `omnichannel/security_authority.py`, `authority_migrations.py`, SQL 005 et
  `api/distributed_security.py`. Conservation de l'admission partagée, révocation
  exclusive, absence de cache positif, CAS et audit transactionnel. Seuls les
  grants `user` et `api` sont repris, dans `rkjo_kernel.security` ; aucun transport
  omnicanal, compte fournisseur ni endpoint métier ajouté. L'API contrôle les
  grants courants avant le handler ; le worker les relit depuis le propriétaire
  persistant L1 avant l'appel de l'agent. Même ordre de verrous : autorité puis
  workflow. Une révocation réussie attend les opérations déjà admises ; les
  opérations suivantes sont refusées. Un audit impossible refuse également
  l'admission. Administration via interface Python d'opérateur de confiance,
  jamais une route ni une instruction issue d'un message.
- **SEC-05** : signature/JWKS, issuer, audience, kid et dates restent vérifiés par
  le code existant. Le claim signé est mappé par une liste explicite contrôlée par
  l'opérateur. Tenant absent/inconnu, type incorrect ou claim contradictoire :
  refus. Configuration absente/invalide : erreur 503, jamais un tenant implicite.
  Un principal OIDC est `oidc:<sha256(issuer)>:<sub>` ; il n'est pas confondu avec
  un principal JWT local. Les grants SQL doivent utiliser ce nom canonique.

La migration L2 est additive et explicite, avec checksum et verrou. Son historique
`001_principal_authority.sql` n'est pas déclaré compatible avec une base S1 déjà
migrée en SQL 005 : un historique différent est refusé et nécessite une migration
revue séparément. Aucun environnement existant ou de production n'est migré ici.

## Configuration livrée

| Variable | Contrat |
| --- | --- |
| `RKJO_SECURITY_PROFILE` | `local` pour tests/bibliothèques locaux ; `distributed` exige l'autorité. Valeur inconnue : refus de démarrage. |
| `RKJO_SECURITY_AUTHORITY_DATABASE_URL` | DSN explicite identique dans API et worker. Absent en distributed : refus. Présent en local : refus, pour éviter une garde silencieusement ignorée. |
| `RKJO_OIDC_ISSUER`, `RKJO_OIDC_AUDIENCE`, `RKJO_OIDC_JWKS_URL` | Source de confiance administrée ; jamais extraite d'un token avant vérification. |
| `RKJO_OIDC_TENANT_CLAIM` | Nom exact d'un claim scalaire signé par l'IdP. |
| `RKJO_OIDC_TENANT_MAP` | Objet JSON explicite claim externe → tenant canonique ; aucune valeur par défaut. |

Le Compose applicatif choisit `distributed` par défaut pour API et worker ; il
refuse donc le démarrage si le DSN n'est pas fourni. `compose.security.yml`
permet aussi une composition explicitement sécurisée. Le retour au profil local
est une configuration explicite, sans prétention de révocation distribuée.

Avant le démarrage sécurisé, sur une base dédiée préparée par l'opérateur :

```bash
python -m rkjo_kernel.security.schema_bootstrap
```

Les variables de profil et de DSN doivent déjà être exportées. Cette commande
n'accorde aucun droit. Provisionnement depuis un outil opérateur de confiance :

```python
from rkjo_kernel.security.configuration import authority_from_env
from rkjo_kernel.security.authority import user_claim, api_claim

authority = authority_from_env()
# Valeurs d'exemple ; sélectionner tenant/principal depuis une source de confiance.
authority.change(user_claim("tenant-a", "principal-canonique"),
                 enabled=True, expected_version=0, actor="operateur-identifie")
authority.change(api_claim("tenant-a", "principal-canonique", "operator"),
                 enabled=True, expected_version=0, actor="operateur-identifie")
# Révocation CAS ; une version périmée n'écrase jamais une décision récente.
authority.change(user_claim("tenant-a", "principal-canonique"),
                 enabled=False, expected_version=1, actor="operateur-identifie")
```

## Recette reproductible dédiée

Python 3.12, Docker Compose, dépendances `requirements-test-lock.txt` inchangées.
Utiliser un venv dédié et une copie sans `.env`. La CI fournit cet environnement.
Les noms de projets ci-dessous ne doivent pas servir à une autre campagne.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-test-lock.txt
.venv/bin/python -m pip install --no-deps ./platform/kernel
docker compose -p rkjo-l1-l2-recette -f compose.l1.yml up -d --wait
docker compose -p rkjo-l2-oidc-recette -f compose.l2-oidc.yml up -d
.venv/bin/python scripts/l2_test.py --project rkjo-l1-l2-recette --oidc-project rkjo-l2-oidc-recette tests/l2 -q --junitxml=.test-results/l2-acceptance.xml
.venv/bin/python scripts/l1_ci_summary.py --suite l2 --junit .test-results/l2-acceptance.xml --output .test-results/l2-summary.json
```

Le runner réutilise la sélection des services dédiés L1, efface les DSN hérités,
configure explicitement l'autorité et attend le vrai discovery OIDC. Il démarre
les commandes livrées `uvicorn rkjo_api.main:app`, `rkjo_worker.main`,
`rkjo_worker.workflow_result_consumer` et `rkjo_worker.outbox_worker` ; aucune
factory n'est remplacée. Les processus d'administration concurrents sont distincts.

Le vrai IdP de recette est Keycloak 26.8.2, en développement isolé sur localhost,
avec import de realm selon la [documentation officielle](https://www.keycloak.org/server/importExport).
Les clients techniques synthétiques émettent des jetons `client_credentials`.
Le claim `organization` est fixé par les mappers serveur, pas par la demande de
jeton. Mapping de recette soumis à validation avec cette PR :
`external-a → tenant-a`, `external-b → tenant-b`. Aucun IdP, login utilisateur,
RKJO Identity, PIN, Face ID ou mapping de production n'est créé.

| Test processus dans `tests/l2/test_authorization.py` | Assertion de sortie |
| --- | --- |
| `test_document_mutations_two_tenants_and_no_legacy_fallback` | Jetons A/B, expiré, absent, inconnu et non lié ; refus sans changement SQL ; A remplace/supprime son document, B reste intact. |
| `test_queued_work_revoked_before_worker_admission` | Tâche réellement en RabbitMQ, révocation avant consumer ; DLQ, aucune sortie agent/résultat ; regrant CAS explicite puis reprise légitime. |
| `test_authority_unavailable_refuses_http_and_worker_without_effect` | Table de grants indisponible : HTTP 503 et aucun appel agent admis ; restauration puis succès. |
| `test_concurrent_grants_cas_and_durable_audit_across_processes` | Deux opérateurs processus : un changement et un conflit, une révocation auditée ; décision relue via une nouvelle autorité. |
| `test_audit_failure_refuses_before_operation` | Audit indisponible : 503, aucune création workflow. |
| `test_revocation_waits_for_admitted_operation_and_migration_integrity` | Verrou exclusif en attente observé dans SQL jusqu'à libération de l'admission ; checksum de migration altéré refusé. |
| `test_real_oidc_tenant_mapping_and_foreign_expired_forged_tokens` | Vrais JWT/JWKS : A réussit jusqu'au résultat durable, B ne lit/démarre pas A, tenant étranger/absent, expiration et signature falsifiée refusés. |

Les tests unitaires complémentaires emploient des claims OIDC décodés simulés
pour les configurations invalides ; ils ne sont pas la preuve IdP. Les embeddings
du test documentaire proviennent du fournisseur déterministe déjà livré. Aucun
LLM ni fournisseur documentaire externe n'est requis pour une garde d'autorisation.

Régression et maintien L1, avec Poppler/Tesseract/fr pour la suite complète :

```bash
.venv/bin/python scripts/l1_test.py --project rkjo-l1-l2-recette tests --ignore=tests/l2 -q --junitxml=.test-results/regression-with-l1.xml
```

La CI sépare régressions, L1 et L2, exige 7 noms L2 et 8 noms L1, zéro skip et les
55 versions verrouillées exactes. Packaging et contrôles web restent actifs.
Seuls les résumés JSON filtrés sont téléversés. Les JWT ne sont conservés que par
empreintes ; chronologies, SQL et logs locaux restent dans `.test-results/l2`.

Après conservation locale des preuves :

```bash
docker compose -p rkjo-l2-oidc-recette -f compose.l2-oidc.yml stop
docker compose -p rkjo-l1-l2-recette -f compose.l1.yml stop
```

## Limites du lot

La révocation intervient à l'admission, sans annuler un effet déjà accepté. Les
résultats d'un travail admis peuvent être enregistrés ; chaque étape suivante
est réautorisée avant son effet. Une tâche refusée reste durable et finit en DLQ
après les retries existants ; aucune annulation métier ni remise en file générale
n'est ajoutée. SQL, le provisioning et la configuration IdP sont de confiance.

Le verrou global S1 privilégie une sémantique claire ; capacité/haute disponibilité,
RLS, droits SQL de production, streaming de permissions et déploiement restent
hors de ce lot. L'IdP qualifié est celui de la recette neutre, sans revendication
d'intégration à une organisation existante. Aucun autre lot n'est engagé.
