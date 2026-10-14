# RKJO Education — Sprint 01 / retour formatif du professeur IA
14 octobre 2026 — CDC V5.0 — Branche feat/edu-health-study-pipeline-v1

## Besoin
Pour une question du cours, l'apprenant donne un raisonnement personnel. RKJO doit proposer des conseils guidés, reliés aux sources, et une question de relance, sans prétendre certifier la maîtrise.

## Livré
- Nouvelle API POST /education/tutor/feedback.
- Requête : course_id, assessment_id, question_id, student_answer (1-3000), help_requested.
- Identité : tenant et apprenant exclusivement depuis le Bearer individuel vérifié par le middleware ; clé opérateur seule refusée.
- Résolution de l'évaluation côté serveur ; lien course_id et présence question_id obligatoires.
- Réutilisation du TutorService et du RAG filtré tenant/document du cours.
- Demande explicite de retour formatif et de reconnaissance d'une source insuffisante.
- Réponse : answer, sources, graded=false, mastery_updated=false.
- Rôle VIEWER pour cette nouvelle route ; ancienne /education/tutor/ask reste OPERATOR.
- Tests unitaires API pour l'identité, l'ownership, l'absence de notation et la RBAC.

## À ne pas considérer comme livré
- Le raccordement PWA reste bloqué par la session pilote partagée, qui ne constitue pas une identité individuelle.
- Pas de correction déterministe vérifiée à partir d'un barème de référence.
- Pas d'écriture au Learner Model ni de décision de maîtrise.
- L'IA peut produire des conseils incorrects : les sources et l'évaluation indépendante restent nécessaires.
- Ces tests API avec middleware simulé ne remplacent pas un E2E avec JWT réel et PostgreSQL.

## Recette
```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-education-health
git pull --ff-only
PYTHONPATH=domains/education:platform/kernel:platform/api \
/Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m pytest -v \
  tests/education/test_tutor_formative_feedback.py \
  tests/education/test_student_identity_guard.py \
  tests/education/test_sprint01_course_navigation_contract.py \
  tests/education/test_guided_learning_ui_contract.py
npm --prefix apps/web run lint
npm --prefix apps/web run build
```
