# L3 — contexte mémoire, LLM et RAG gouvernés

Base : `cf7c08dc7a824f747949496e0f5738240dabd649`, fusion L2 #16.
Périmètre : KRN-02, MEM-03, LLM-01/02/03/04, RAG-07. Aucun autre lot.

## Contrat livré et provenance

La composition `RKJOKernel` de S1 `ada39d0d11ec2e8f0d3dc276e99ad4b1e133414c`
est reprise sélectivement, avec propriété des clients et arrêt idempotent.
`LLMBackedAnswerGenerator` et les tests `tests/kernel/llm` proviennent de
`feat/platform-llm-port-v1@189a3e4beca635b41e05517b66e31c050e587dda` ; les tests
sont adaptés aux nouveaux plafonds. Aucune branche entière n'est fusionnée.

`build_platform_kernel` compose la mémoire PostgreSQL, ContextEngine,
AgentContextRuntime, le registre injecté, les outils et la passerelle configurée.
L'API et le worker utilisent cette même factory pour mémoire/LLM. Les factories
workflow L1 et l'autorité L2 sont réutilisées. Les composants de bibliothèque
restent injectables sans PostgreSQL. Le kernel ferme uniquement les ressources
dont il est propriétaire ; un kernel fermé doit être reconstruit.

Le worker livré raccorde automatiquement la mémoire **de mission** après
admission L1/L2, avant l'agent. Tenant/mission absents sont refusés dans un runtime
sécurisé. Limites : 12 éléments, 5 000 caractères de contenu ; l'adaptateur LLM
borne le bloc final avec provenance à 6 000 caractères. Les références restent
des données dans un message utilisateur, jamais des instructions système.

Un workflow neutre lancé par `platform_task` peut demander explicitement :

```json
{"input_data":{"operation":"rag_answer","question":"Quel est le code du coffre Atlas ?"}}
```

Le comportement générique antérieur reste disponible. La réponse documentaire
contient réponse, citations et identifiants de contexte, puis suit la publication
et la persistance L1. Un champ `question` seul n'active pas le fournisseur.
Le worker n'accepte pas un contexte d'autorité depuis `input_data`.

`POST /rag/answer` passe désormais par la même passerelle, avec tenant authentifié
et mission/trace générés par le serveur. Chaque requête HTTP indépendante crée
une mission ; ce lot n'introduit pas de conversation ni de quota global tenant.
Le kernel est créé après validation et vérification du tenant, puis fermé dans
`finally`. Le générateur OpenAI direct existe encore comme bibliothèque historique,
mais n'est plus construit par les factories API/worker.

## Politique, budgets et erreurs

La configuration serveur et les contraintes du contexte se combinent dans le
sens le plus restrictif. `local-only` bloque OpenAI avant tout appel réseau et
bloque aussi les embeddings distants avant la recherche. Une URL Ollama distante
ne peut pas se déclarer locale : la factory exige HTTP loopback sans credentials.
Les trois IDs tenant/mission/trace sont transmis en en-têtes `X-RKJO-*-id`, encodés
URL, et conservés dans les reçus SQL. Aucun rôle, secret ou corps de politique
n'est transmis comme en-tête.

Le profil livré choisit **un fournisseur, sans fallback ni retry SDK implicite**.
Le routeur de bibliothèque conserve ses contrats de fallback, testés séparément.
Aucun prix monétaire n'est inventé : `max_cost` non nul est refusé avant appel.

Avant appel, on calcule des unités d'admission conservatrices : octets UTF-8 des
messages + 256 par message. Ce n'est pas un tokenizer exact ni une garantie de
facturation du fournisseur. La sortie est limitée via `num_predict` /
`max_output_tokens`. PostgreSQL réserve atomiquement entrée + sortie pour la paire
(tenant, mission), sous verrou. Après succès, l'usage déclaré est enregistré et
la réserve ajustée ; dépassement ou usage incohérent est refusé. Usage manquant,
timeout ou erreur : aucune fausse réponse réussie, réservation conservée comme
incertaine. Après crash, une réservation persistante reste débitée. Une redelivery
peut créer une nouvelle tentative si le budget restant le permet : ce lot ne
promet pas un effet LLM exactement une fois ni un remboursement automatique.
Les reçus ne stockent ni prompts ni réponses : IDs, hash, limites, modèle, usage,
latence et état. La base reste une ressource de service de confiance.

## Configuration explicite

| Variable | Règle |
| --- | --- |
| `RKJO_DATABASE_URL` ou `DATABASE_URL` | DSN explicite pour la composition durable. |
| `RKJO_LLM_PROVIDER` | Vide : génération indisponible ; `ollama` ou `openai` explicite. |
| `RKJO_LLM_MODEL` | Obligatoire lorsque le fournisseur est choisi. |
| `RKJO_LLM_LOCAL_ONLY` | `true` par défaut ; `false` explicite pour autoriser l'externe, sous réserve de la politique du contexte. |
| `RKJO_LLM_TIMEOUT_SECONDS` | Entier positif, 60 par défaut. |
| `RKJO_LLM_MAX_INPUT_TOKENS` | Plafond d'admission, 32768 par défaut. |
| `RKJO_LLM_MAX_OUTPUT_TOKENS` | Limite de sortie, 512 par défaut. |
| `RKJO_LLM_MAX_TOTAL_TOKENS` | Budget cumulatif par tenant/mission, 65536 par défaut. |
| `RKJO_OLLAMA_BASE_URL` | HTTP loopback, défaut `http://127.0.0.1:11434`. |
| `OPENAI_API_KEY` | Seulement si OpenAI est explicitement sélectionné ; aucune valeur de recette dans le runtime. |
| Variables embedding/retrieval/reranking existantes | Conservées ; recette déterministe 16 dimensions, hybride, reranker lexical, minimum_results=0. |

Le Compose transmet les mêmes paramètres à API/worker, sans activer de fournisseur
par défaut. Les anciennes variables `RKJO_GENERATION_*` sont remplacées par
`RKJO_LLM_*`. Le fournisseur réel est qualifié dans des processus natifs locaux ;
le loopback d'un conteneur est son propre espace réseau. Ce lot ne qualifie pas
un déploiement Ollama en conteneur ni un endpoint distant comme local.

## Recette reproductible

Prérequis : Python 3.12, Docker Compose, copie sans `.env`, modèle **déjà installé**
`qwen3:8b` dans Ollama local. Aucun téléchargement automatique de modèle.
Digest exigé : `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
Les commandes ne doivent viser que le projet dédié indiqué.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-test-lock.txt
.venv/bin/python -m pip install --no-deps ./platform/kernel
mkdir -p .test-results
docker compose -p rkjo-l1-l3-recette -f compose.l1.yml up -d --wait
.venv/bin/python scripts/l3_test.py --project rkjo-l1-l3-recette tests/l3 -q --junitxml=.test-results/l3-acceptance.xml
.venv/bin/python scripts/l1_ci_summary.py --suite l3 --junit .test-results/l3-acceptance.xml --output .test-results/l3-summary.json
.venv/bin/python scripts/l1_test.py --project rkjo-l1-l3-recette tests --ignore=tests/l1 --ignore=tests/l2 --ignore=tests/l3 -q --junitxml=.test-results/regression.xml
.venv/bin/python scripts/l1_ci_summary.py --suite regression --junit .test-results/regression.xml --output .test-results/regression-summary.json
.venv/bin/python scripts/l1_test.py --project rkjo-l1-l3-recette tests/l1 -q --junitxml=.test-results/l1-acceptance.xml
.venv/bin/python scripts/l1_ci_summary.py --suite l1 --junit .test-results/l1-acceptance.xml --output .test-results/l1-summary.json
docker compose -p rkjo-l1-l3-recette -f compose.l1.yml stop
```

Le runner enlève les variables RKJO/DB/broker/OpenAI héritées, refuse `.env`, vérifie
les ports loopback du projet dédié, un écart d’horloge PostgreSQL/processus inférieur
à 0,5 seconde, et le digest du modèle. Un écart supérieur bloque la recette ;
le runner ne corrige pas l’horloge et ne relance pas automatiquement. Il ne copie aucun
mapping OIDC L2. La recette provisionne ses grants synthétiques dans sa base L3.
La preuve du transport utilise un proxy loopback qui **transmet réellement** à
Ollama : aucune réponse synthétisée, aucun override de gateway/factory. Les corps
observés sont exclusivement ceux du corpus neutre.

Les refus et timeouts sont dans `tests/kernel/llm/test_governed_composition.py` :
SQL et clients HTTP réels, serveur local contrôlé pour erreurs, timeout, usage
absent/excessif ; ce serveur n'est pas présenté comme une preuve de qualité LLM.
OpenAI conserve des tests de contrat avec double SDK ; aucun appel OpenAI réel.
La CI exécute ces contrats dans les régressions, plus L1/L2 réels. Les deux tests
`tests/l3` nécessitent Ollama et sont explicitement une recette locale distincte,
jamais des tests CI prétendument réussis par skip.

## Évaluation bornée et preuves

`tests/l3/corpus.json` est figé avant le premier run : deux faits répondables,
un cas sans réponse et un document contradictoire d'un autre tenant.
Seuils : hit@3=1, MRR=1, fidélité des faits attendus=1, abstention correcte=1.
La fidélité est une mesure de cette recette : concept attendu, absence des valeurs
contradictoires, source attendue et marqueurs valides ; les réponses neutres sont
conservées pour revue humaine. Ce n'est pas un score général de non-hallucination.
La recette vérifie en plus le hash du prompt au transport, l'absence de mémoire B,
le bornage, les mêmes IDs et l'usage dans les reçus durables.

Chaque run a son propre dossier `.test-results/l3/run-*`. Conserver JUnit,
configuration expurgée, corpus, résultats et chronologie des processus dans les
preuves privées ; publier seulement un résumé relu et les réponses neutres.
Aucun log brut ni archive de base n'est publié. Qualification de production,
GraphRAG, nouveaux modèles, tuteur métier et lots suivants sont hors périmètre.
