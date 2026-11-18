# Bilan L3 — contexte mémoire, LLM et RAG gouvernés

**L3 fusionné ; livraison du correctif L3-CI-01 BLOQUÉE au 17 novembre 2026.**
Le correctif PR #18 passe 10/10 démarrages froids et les contrôles backend CI ;
le contrôle npm audit reste rouge, sans version amont corrigée publiée.
La consolidation reste à ce4de07 ; PR #18 non fusionnée, L4 non engagé.

Constat historique avant le correctif :
La première CI post-fusion échoue dans L1 (7 succès, 1 erreur, 0 skip).
Le prochain lot n'est pas engagé. Les sept preuves fonctionnelles L3 ci-dessous
restent distinctes de cette qualification de livraison non acquise.
Base L2 fusionnée `cf7c08dc7a824f747949496e0f5738240dabd649`.
Code applicatif `2df5b2ec7d481ff64bca19168b06e61370d89d33` ; recette qualifiée
avec précontrôle d’horloge au SHA `92e2194e3d0d1add48cf77d39c877ea45549a886`.
Le commit suivant ajoute uniquement ce bilan et le résumé de preuves.

L2 #16 a été fusionnée au HEAD autorisé `3780e4c4fdf6fa727141024456a0945eade8cddd`
après checks/revues/diff vérifiés, sans contournement et en conservant la branche.
Sa [CI post-fusion](https://github.com/sowhatt/rkjo-ai-platform/actions/runs/43698419251)
a réussi dès la première tentative : 7 L2, 8 L1, 1395 régressions, zéro skip,
packaging et web verts. Les lignes SEC-02/04/05 de la matrice d’audit locale sont
TERMINÉ/A au SHA fusionné. Le mapping L2 demeure exclusivement accepté pour la
recette ; aucune configuration de production n’en est déduite.

## Exigences L3 et preuves

| ID | Résultat fonctionnel, code désormais intégré A | Preuve |
| --- | --- | --- |
| KRN-02 | TERMINÉ sur le périmètre composition bibliothèque + mémoire/LLM des points d’usage API/worker | Composition S1 reprise ; factory commune ; arrêt client une fois ; import du paquet installé hors dépôt. |
| MEM-03 | TERMINÉ | Processus worker livré arrêté puis recréé ; SQL conserve mémoire A ; contexte borné ; mémoire B et élément surdimensionné absents du transport fournisseur ; contexte canonique absent refusé en mode sécurisé. |
| LLM-01 | TERMINÉ sur le profil mono-fournisseur borné du lot | Client OpenAI réel configuré face à un serveur de contrôle : zéro requête en local-only ; politique de contexte restrictive bloque aussi embeddings ; réservation SQL concurrente atomique ; budget consommé bloque un nouvel appel après reconstruction de factory. |
| LLM-02 | TERMINÉ | Factory documentée pour Ollama/OpenAI ; timeouts et erreurs HTTP contrôlés ; sortie plafonnée ; usage manquant/excessif refusé ; contrat OpenAI avec double SDK ; Ollama réel. |
| LLM-03 | TERMINÉ | `POST /rag/answer` natif et workflow neutre `platform_task → rag_answer` utilisent le générateur repris et le gateway ; aucun override de factory ; IDs concordants entre workflow, en-têtes réels et reçus SQL. |
| LLM-04 | TERMINÉ pour Ollama `qwen3:8b` | 4 appels réels dans les 2 tests nommés ; digest/configuration/usage/latence conservés, reçus sans texte sensible. |
| RAG-07 | TERMINÉ pour le corpus neutre figé du lot | Deux faits, un cas sans réponse, document B contradictoire ; hit@3=1, MRR=1, fidélité des faits/citations=1, abstention=1 ; zéro citation invalide. |

**7/7 critères fonctionnels L3 démontrés dans leur périmètre borné.** Le code
est intégré à la consolidation au SHA `ce4de07cee91c92ddbf6c9a8206b5f56ec2f3891`.
Le blocage transverse `L3-CI-01` ci-dessous est enregistré une fois et relié aux
sept lignes de matrice ; leur clôture fonctionnelle n'est pas une acceptation
de la livraison post-fusion. Aucun nouveau pourcentage global n'est calculé.

Résultats : deux tests de recette réelle réussis sans skip ; 1 445 régressions
sans skip, dont 14 contrats L3 à serveur HTTP contrôlé ; huit L1 sans skip.
Les 55 versions du lock CI sont exactes. Les deux tests de fournisseur réel sont
une recette locale explicite ; la CI n’est pas présentée comme les exécutant.
Les checks du HEAD de la PR constituent la preuve CI complémentaire à consulter.

Recette et commandes : [L3_EXECUTION.md](../llm/L3_EXECUTION.md).
Preuves publiables : [L3_QUALIFICATION.json](L3_QUALIFICATION.json).
La première campagne applicative a passé ses deux tests ; une exécution ultérieure
au SHA applicatif a échoué au démarrage d’un workflow, avant son appel LLM.

## Première erreur conservée et limite de diagnostic

`l3-candidate.xml` : un échec, un succès ; HTTP 503 « No available workflow agent »
après redémarrage du worker. Le journal annonce AVAILABLE avant la requête.
Le timestamp conservé du registre est inférieur d’environ 292 secondes à l’arrêt
journalisé du processus. C’est compatible avec un décalage transitoire de l’horloge
Docker, qui ferait expirer le bail de trois secondes. **La causalité n’est pas
confirmée** : la ligne avant dispatch n’avait pas été capturée, et le nettoyage
normal de la régression a supprimé le workflow avant la comparaison SQL ultérieure.
Aucun défaut de génération/mémoire n’est démontré par cette erreur ; elle n’est
pas effacée ni présentée comme corrigée dans L1.

Action limitée à la recette L3 : précontrôle des horloges avec refus au-delà de
0,5 seconde et capture du registre avant dispatch. Aucun changement du runtime
L1, aucune augmentation du bail, aucun retry de la requête 503. Une exécution
après cette instrumentation a passé les deux tests ; skew mesuré **0,001357 s**.
Le premier JUnit, stdout, logs et diagnostic sont conservés dans
`.git/l3-local-evidence/first-candidate-failure/`, hors publication.

## Limites et conservation

La fidélité mesure les faits/citations de trois questions fixes, avec réponses
neutres conservées pour revue ; elle ne prouve pas une qualité générale sur des
corpus utilisateurs. OpenAI n’a pas été appelé réellement. Les budgets sont par
mission, sans prix monétaire ni quota tenant global. Les effets LLM incertains
restent débités ; aucune garantie exactement-une-fois supplémentaire n’est ajoutée.
La cohérence d'horloge est un prérequis, sans attribution causale de l'ancien 503.

Les modifications et preuves sont durables dans la copie isolée L3 sous Projects.
Les WIP du dépôt d’origine sont préservés. Gitleaks du delta : zéro détection ;
seuls des résumés filtrés et le corpus/réponses synthétiques sont publiés.
Aucun log brut, JWT, DSN réel ni archive de preuves n’est ajouté à Git.
La fusion L3 autorisée est décrite ci-dessous. Aucune fusion vers main,
installation de modèle, mise en production, fonctionnalité Identity/PIN/Face ID
ou implémentation d'un autre lot n'est engagée.

## Finalisation du 17 novembre : provenance et fusion

[PR #17](https://github.com/sowhatt/rkjo-ai-platform/pull/17) : HEAD vérifié
`30c4d39061548973e205593594270b8350b55b7f`, cible
`feat/platform-consolidation-20261109`. Diff limité à L3, 36 fichiers ; aucune
modification de code effectuée pendant cette finalisation. Revues, fils de revue
et commentaires de discussion consultés : aucune objection. Aucune protection
de branche ni règle effective n'était configurée ; aucun contournement utilisé.
Les quatre jobs étaient verts sur ce HEAD avant sortie du brouillon et fusion.
La branche candidate est conservée.

La [CI pré-fusion 43717291432](https://github.com/sowhatt/rkjo-ai-platform/actions/runs/43717291432)
a testé le commit synthétique `b1f25a61b695b7e8eba0fc5e0144f5507dbd13b9`, dont
les parents sont la base `cf7c08dc7a824f747949496e0f5738240dabd649` et le candidat
`30c4d39061548973e205593594270b8350b55b7f`. Le vrai commit fusionné
`ce4de07cee91c92ddbf6c9a8206b5f56ec2f3891` a les mêmes parents. Leurs arbres et
celui du candidat sont identiques : `ce009755a712e27d7134af4c1dc1e095e6a680c9`.
Cela relie le code testé au code livré, sans confondre les SHA de commit.

| Campagne | Résultat | Fournisseur réel |
| --- | --- | --- |
| Recette locale L3 conservée, 92e2194… | 2 tests, 2 succès, 0 skip ; 4 appels Ollama `qwen3:8b` | Oui, quatre appels ; aucun nouvel appel le 17 novembre |
| CI pré-fusion 43717291432, tentative 1 | 1 445 régressions + 8 L1 + 7 L2, zéro échec/erreur/skip ; web et packaging verts | Non ; contrats fournisseur contrôlés, recette Ollama exclue |
| Découverte ciblée du 17 novembre, 30c4d3… | Une exécution, un redémarrage, un POST/start : 202 puis completed, un dispatch durable | Non, zéro appel ; scénario neutre isolant la découverte |
| CI post-fusion 44116538750, tentative 1, ce4de07… | 1 445 régressions et 7 L2 réussis, zéro skip ; web/packaging verts ; L1 : 7 succès, 1 erreur, zéro skip | Non |

Les résumés CI vérifient 55 versions verrouillées. Les résultats de corpus sont
ceux de trois questions fixes avec embeddings déterministes et reranker lexical,
pas une qualification générale du RAG, des embeddings ou des modèles.

## Découverte du worker : reproduction bornée

Le protocole a été écrit avant l'exécution, hash SHA-256
`ee1839f6db297c4704139b1def0c27a3fce27b574a2e130c789aaa01fe4690cd`.
API/worker/results/outbox livrés, PostgreSQL et RabbitMQ du projet dédié
`rkjo-l1-l3-discovery-20261117`, dépendances verrouillées, sans override.
Critères fixés : un redémarrage, nouvel instance_id AVAILABLE, bail inchangé de
3 s et âge inférieur à 3 s, écart SQL/processus au plus 0,5 s, un seul POST/start
202, completed dans 30 s, un dispatch et une sortie, zéro appel LLM.
Tous satisfaits : âge du bail après redémarrage 0,024771 s ; temps SQL compris
entre les deux captures du processus. Ni retry de POST, ni allongement de bail.

Cette réussite démontre le scénario sur ce candidat ; elle ne démontre pas la
cause de l'ancien 503. Les captures anciennes ne suffisent pas pour conclure à
un décalage d'horloge. L'ancien échec et ses traces sont conservés intactement.
Protocole, script et résultats privés :
`.git/l3-local-evidence/finalization-20261117/` dans la copie durable L3.

## L3-CI-01 — blocage post-fusion, sans relance

[CI 44116538750](https://github.com/sowhatt/rkjo-ai-platform/actions/runs/44116538750),
événement push, tentative 1, checkout/candidate
`ce4de07cee91c92ddbf6c9a8206b5f56ec2f3891`.
[Job L1 134156026296](https://github.com/sowhatt/rkjo-ai-platform/actions/runs/44116538750/job/134156026296).
Le seul cas en erreur est
`tests.l1.test_acceptance.test_two_steps_restart_and_insert_only` (2,337 s).
Le résumé indique `error`, pas `failure` ; la phase précise setup/teardown et
l'exception ne sont pas conservées dans l'artefact publié. Les sept autres cas
passent. On ne peut donc pas conclure « assertion fonctionnelle en échec »,
« test instable », « même HTTP 503 » ou « horloge décalée ».

Limite démontrée : le workflow redirige stdout et JUnit dans `.test-results` ;
`scripts/l1_ci_summary.py` n'exporte que noms, durées, statuts, versions et SHA.
Le job publie seulement `l1-summary.json`. Le journal Actions conservé contient
les codes de sortie, pas l'exception ; le runner éphémère et ses services ont
été arrêtés. Il manque donc la première exception et les logs des processus
pour attribuer cette nouvelle erreur. Aucun correctif spéculatif n'est ajouté.
Aucune relance de la CI n'a été demandée.

Déblocage nécessaire dans L3 : capturer de façon expurgée la classe d'exception,
la phase pytest, les frames du dépôt, le service/processus sortant et les faits
de readiness du premier cas sur infrastructure neuve. Fixer un protocole de
diagnostic avant une unique exécution ; conserver le premier échec. Corriger
uniquement un défaut attribué à L3, ou établir précisément l'instabilité de
recette avant une requalification justifiée. Un succès isolé ne prouverait pas
la cause de cette erreur. Responsable : qualification du socle, à affecter.
Sortie du blocage : explication étayée et CI de qualification complète réussie
sur le SHA de consolidation retenu, sans tests ignorés ni protections contournées.

Les métadonnées du run, les trois résumés et le journal du job sont conservés
privément dans `.git/l3-local-evidence/postmerge-44116538750/`. Aucun log brut
ni archive n'est publié. Le manifeste initial (50 fichiers) est vérifié intact ;
un manifeste additionnel couvre les nouvelles preuves sans remplacer l'ancien.

Le prochain lot lu dans le plan est exactement **L4 — outils sensibles et
transports MCP** (`TLS-02/04/06`). Ses bases L1/L2 et les composants MCP existent,
mais le préalable imposé de réussite post-fusion L3 n'est pas satisfait.
**L4 n'est pas commencé ; aucune PR L4 n'est créée.**

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
