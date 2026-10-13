# Streams C + F — raccordement évaluation → preuve → prochaine action
13 octobre 2026 — branche isolée `feat/edu-health-study-pipeline-v1`

## Livré
- `domains/education/rkjo_education/learning/assessment_action_bridge.py` : raccordement déterministe entre un `Attempt` soumis, sa `Question` dans l'`Assessment`, une éventuelle `StoredProofChallenge` / `ProofResult`, et la politique existante `recommend_next_action`.
- `tests/education/test_assessment_action_bridge.py` : diagnostics, erreurs, aides, prérequis, preuve validée, séparation tenant/étudiant, compétence incompatible, tentative non soumise.
- Aucun appel LLM, aucune mutation de `main`, aucune donnée réelle.

## Conditions
Le raccordement n'interroge **pas** lui-même PostgreSQL et n'authentifie pas l'appelant. Les enregistrements doivent être lus dans les dépôts sécurisés avec tenant et identité provenant du serveur. Le résultat de preuve doit provenir de `ProofApplicationService`, jamais d'un corps JSON transmis par le navigateur. Le contexte complet (question d'origine, cours et compétence) doit être vérifié. Une réponse guidée correcte n'est pas une preuve autonome.

## Recette demandée (Mac)
```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-education-health
git pull --ff-only
PYTHONPATH=domains/education:platform/kernel:platform/api \
/Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m pytest -v \
  tests/education/test_assessment_action_bridge.py
```
**Résultat non encore confirmé** : ce lot a été ajouté directement à GitHub ; l'exécution pytest reste à réaliser localement.

## Suivant
Raccorder les dépôts `AssessmentRepository` et `ProofChallengeRepository` dans un service applicatif tenant-safe. Exposer une réponse API du type `action/reason/competency_code` sans divulguer de corrections d'examen. Intégrer l'état dans `EducationSession.tsx` seulement après tests API d'autorisation, tests de non-régression et démonstration navigateur. Conserver les streams A/B/D/G parallèles.
