# RKJO Education — Next Best Action HTTP (streams C + F)
13 octobre 2026 — branche `feat/edu-health-study-pipeline-v1`

## Ajouts
- `get_education_assessment_action_service()` assemble les repositories PostgreSQL d'évaluation et de preuve.
- `GET /education/attempts/{attempt_id}/questions/{question_id}/next-action` relit les données de tentative et de preuve depuis la base, puis appelle le moteur déterministe.
- `proof_challenge_id` est un identifiant facultatif ; le statut et le résultat ne proviennent **jamais** de la requête HTTP.
- L'API exige `Authorization: Bearer ...` et un sujet étudiant UUID lié au tenant UUID. Elle répond 403 sans identité individuelle, 404 pour la preuve introuvable, 409 pour une incohérence métier.
- Le prérequis ne peut pas être décidé via paramètre client ; ce premier endpoint prend uniquement la valeur conservative par défaut, en attendant le moteur de prérequis persistés.

## Sécurité / limitations
- Le binding sujet Bearer → learner UUID est **une hypothèse de ce pilote** ; si le fournisseur d'identité utilise un autre identifiant, implémenter un mapping explicite sécurisé avant exposition dans la PWA.
- Les conditions « proof PASSED » supposent que seul le service serveur `ProofApplicationService` peut produire ou modifier ce statut ; ne pas exposer les écritures directes.
- **Ne pas déclarer production-ready** avant validation du RBAC réel, tests d'intégration PostgreSQL, et vérification de l'appartenance des tentatives/épreuves.
- Ce lot ne modifie pas `EducationSession.tsx` ni le comportement des autres streams.

## Tests Mac
```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-education-health
git pull --ff-only
PYTHONPATH=domains/education:platform/kernel:platform/api \
/Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m pytest -v \
  tests/education/test_assessment_action_bridge.py \
  tests/education/test_assessment_action_service.py \
  tests/education/test_assessment_next_action_api.py
npm --prefix apps/web run lint
npm --prefix apps/web run build
```
Ces nouveaux tests n'ont pas encore été exécutés sur le Mac dans cet échange.
