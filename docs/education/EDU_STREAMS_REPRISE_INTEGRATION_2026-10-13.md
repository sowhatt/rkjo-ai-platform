# RKJO Education — reprise des streams et intégration Learner First
Date : 13 octobre 2026
Branche : `feat/edu-health-study-pipeline-v1`
Statut : plan d'intégration basé sur la lecture du dépôt, **pas** recette de production.

## Périmètre vérifié
- Comparaison GitHub `main...feat/edu-health-study-pipeline-v1` : 209 commits d'avance, 0 en retard au relevé du 13/10/2026 ; ceci ne mesure **ni** la couverture fonctionnelle **ni** l'aptitude à la production.
- Composants existants observés : `EducationSession.tsx`, `StudyPdfPreview.tsx`, `EducationHome.tsx`, `next_action_policy.py`, `proof_application.py`, `assessment/service.py`, `study_audio_rehearsal.py`, routes `/education/study/*`.
- Tests PostgreSQL de l'audio : 4 tests annoncés « passed » sur Mac par le développeur ; aucune exécution CI complète n'a été effectuée dans cet audit.
- Historique validé : `HEALTH_STUDENT_STREAMS_2026-10-11.md`, `EDU_AUDIO_BOOK_TRANSLATION_STREAMS_V1.md`, `EDU_STREAMS_B_D_REVISION_MAP_V1.md`. Ne pas renommer les streams.

## Objectif vertical P0 : source → révision → preuve → prochaine action
Sur une UE de démonstration avec données fictives, permettre :
1. Sélection de filière, année et UE ; import d'un **PDF textuel fictif** avec pages et provenance.
2. Prévisualisation et fiche sourcée (déterministe par défaut ; option IA clairement signalée si activée et autorisée).
3. Activité évaluative **réelle et déterministe** (questions validées, pas de score créé par LLM).
4. Preuve autonome sans aide et décision Next Best Action justifiée par les données observées.
5. Restitution sur l'espace étudiant avec accès isolé et journal des erreurs.

**Hors P0 tant que les dépendances ne sont pas fiables** : transcription audio réelle, traduction d'ouvrages protégés, paiement, pilotage d'enregistrements sensibles, publication de la file synthétique.

## Streams officiels et incréments en parallèle
| Stream | Responsable fonctionnel | Premier incrément vérifiable | Contrat de sortie / test |
|---|---|---|---|
| **A** | Professeur IA | Présenter une explication guidée rattachée aux pages et aux compétences | Références de segments valides ; refus de citer une source inconnue |
| **B** | UX étudiant | Unifier les passages ressource → fiche → évaluation → progression dans la PWA | Navigation end-to-end, états chargement/échec, labels honnêtes |
| **C** | Learning Engine | Relier évaluation / preuve autonome à `recommend_next_action` | Aucun AVANCE sans preuve ; raisons explicables, tests métier |
| **D** | Documents / RAG / Curriculum | Stabiliser `StudySourcePackage`, segments page/UE, version et invalidation | Provenance, déduplication, liens source → artefact |
| **E** | Multimodal | Conserver la répétition audio synthétique, poursuivre tests crash/rollback **isolés** | Pas de publication ASR ; idempotence et restauration garanties |
| **F** | Identité | Autoriser les ressources et preuves par tenant et étudiant | 403/404 pour accès croisés ; aucune identité client faisant autorité |
| **G** | Model Gateway | Encadrer l'option IA fiches : quota, timeout, coûts et fallback sûr | Mode sans IA fonctionnel, option explicitement consentie |
| **S** | Safety | Contrôler source non fiable, droits, santé, consentement, suppression | Pas de documents patients, pas de fuite ou redistribution |
| **T** | Supervision | Tracer les preuves, corrections et échecs ; recette transverse | Test intégration + navigateur, journal exploitable |

## Contrats partagés — à figer avant raccordement
- `StudySourcePackage`: tenant, learner, programme, UE, source_id, source_version, segments (id/page/texte/provenance), droits et statut.
- `StudyArtifact`: source/version, segment_ids valides, type, modèle/génération, état de validation.
- `LearningEvidence`: learner, compétence, attempt_id, résultat observé, aides utilisées, flag autonome et traçabilité.
- `ActionDecision`: enum `diagnose|remediate|practice|autonomous_proof|advance` + raison. Seul C la décide.
- Toute API valide tenant/learner depuis la session serveur ; les informations fournies par le navigateur ne deviennent jamais des autorisations.

## Règles anti-régression et coordination
- Ne jamais pousser directement sur `main` ; conserver la branche d'intégration isolée.
- Développer un incrément vertical livrable ; plusieurs streams peuvent avancer indépendamment tant que leurs contrats restent stables.
- Chacun livre code + tests ; intégrer seulement après tests contractuels et audit des zones partagées.
- Ne pas inventer de pourcentages : distinguer code présent, tests exécutés, parcours navigateur validé, déploiement.
- Ne pas activer la queue `rkjo.education.audio.synthetic.rehearsal.disabled` : aucun worker ni ASR réel derrière.
- Tout ajout sur base de test doit être réversible. Aucune donnée sensible dans les fixtures.

## Séquence d'exécution
1. **B + D** : route utilisateur stable depuis un PDF fictif vers des fiches sourcées ; conservation des identifiants source/page.
2. **A + G** : génération facultative bornée avec validation de provenance, mode déterministe de repli.
3. **C + F** : épreuve autonome et décision explicable sous isolation stricte.
4. **E + S + T** : résilience audio synthétique et recette transverse sans freiner B/C/D.
5. Démonstration bout en bout ; seulement ensuite élargir aux flashcards, cartes graphiques, ASR et paiement.

## Contrôles de recette Mac
```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-education-health
git branch --show-current
git pull --ff-only
PYTHONPATH=domains/education:platform/kernel:platform/api \
/Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m pytest -q \
  tests/education/test_study_learning_views.py \
  tests/education/test_study_documents_api.py \
  tests/education/test_study_ai_materials_v2.py \
  tests/education/test_study_audio_rehearsal.py \
  tests/education/test_study_audio_staging_postgres.py
npm --prefix apps/web run lint
npm --prefix apps/web run build
```
L'audio PostgreSQL n'est réellement testé que si `RKJO_EDUCATION_AUDIO_TEST_DATABASE_URL` est défini dans le terminal courant. Vérifier que l'environnement de test pointe exclusivement vers la base jetable prévue.
