# Bilan L3 — contexte mémoire, LLM et RAG gouvernés

**Recette technique L3 satisfaite sur le candidat ; validation humaine et fusion
non effectuées.** Base L2 fusionnée `cf7c08dc7a824f747949496e0f5738240dabd649`.
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

| ID | Résultat sur le candidat séparé B | Preuve |
| --- | --- | --- |
| KRN-02 | TERMINÉ sur le périmètre composition bibliothèque + mémoire/LLM des points d’usage API/worker | Composition S1 reprise ; factory commune ; arrêt client une fois ; import du paquet installé hors dépôt. |
| MEM-03 | TERMINÉ | Processus worker livré arrêté puis recréé ; SQL conserve mémoire A ; contexte borné ; mémoire B et élément surdimensionné absents du transport fournisseur ; contexte canonique absent refusé en mode sécurisé. |
| LLM-01 | TERMINÉ sur le profil mono-fournisseur borné du lot | Client OpenAI réel configuré face à un serveur de contrôle : zéro requête en local-only ; politique de contexte restrictive bloque aussi embeddings ; réservation SQL concurrente atomique ; budget consommé bloque un nouvel appel après reconstruction de factory. |
| LLM-02 | TERMINÉ | Factory documentée pour Ollama/OpenAI ; timeouts et erreurs HTTP contrôlés ; sortie plafonnée ; usage manquant/excessif refusé ; contrat OpenAI avec double SDK ; Ollama réel. |
| LLM-03 | TERMINÉ | `POST /rag/answer` natif et workflow neutre `platform_task → rag_answer` utilisent le générateur repris et le gateway ; aucun override de factory ; IDs concordants entre workflow, en-têtes réels et reçus SQL. |
| LLM-04 | TERMINÉ pour Ollama `qwen3:8b` | 4 appels réels dans les 2 tests nommés ; digest/configuration/usage/latence conservés, reçus sans texte sensible. |
| RAG-07 | TERMINÉ pour le corpus neutre figé du lot | Deux faits, un cas sans réponse, document B contradictoire ; hit@3=1, MRR=1, fidélité des faits/citations=1, abstention=1 ; zéro citation invalide. |

**7/7 critères L3 qualifiés sur la branche candidate**, pas 7 éléments déjà
intégrés à la consolidation. Aucun nouveau pourcentage global du socle n’est
calculé. Les statuts L3 historiques de la matrice de consolidation ne sont pas
promus comme fusionnés ; ce tableau distingue la preuve candidate B.

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
Le risque transverse d’horloge reste documenté comme prérequis d’infrastructure.

Les modifications et preuves sont durables dans la copie isolée L3 sous Projects.
Les WIP du dépôt d’origine sont préservés. Gitleaks du delta : zéro détection ;
seuls des résumés filtrés et le corpus/réponses synthétiques sont publiés.
Aucun log brut, JWT, DSN réel ni archive de preuves n’est ajouté à Git.
Aucune fusion L3, fusion vers main, installation de modèle, mise en production,
fonctionnalité Identity/PIN/Face ID ou autre lot n’est engagée.
