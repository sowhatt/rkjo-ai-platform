# RKJO Education — intégration A + C + G (CE1), v1

## Statut
Services de domaine composés, tests ajoutés. **À exécuter sur le Mac**. Pas encore de connexion HTTP ou d'intégration PWA : le professeur de l'interface CE1 V2 reste scénarisé. Aucune persistance des preuves, aucun modèle IA exécuté.

## Composants
- A : `tutor/guided_lesson.py` définit les phases et les demandes d'aide.
- C : `learning/next_action_policy.py` produit une décision explicable.
- G : `model_gateway/task_router.py` produit un plan de routage mathématiques (LLM candidat, SymPy vérificateur), sans exécution réseau.
- Orchestration : `learning/ce1_orchestrator.py` pilote les transitions et garde les essais guidés séparés des preuves indépendantes.

## Contrats importants
- Une réponse guidée correcte ne suffit pas à valider une preuve autonome.
- Aucune aide ni reformulation n'est acceptée pendant la phase de preuve.
- Les indices de la phase guidée ne contaminent pas le statut d'une preuve séparée réalisée sans aide.
- Les transitions invalides sont rejetées.
- Aucun endpoint public non authentifié n'est créé.
- Ne pas exposer un service d'écriture au frontend tant que l'identité individuelle JWT + grants n'est pas vérifiée et testée.

## Validation
```bash
PYTHONPATH=domains/education:platform/kernel:platform/api \
python -m pytest -q --tb=short \
  tests/education/test_guided_lesson_parallel.py \
  tests/education/test_next_action_policy_parallel.py \
  tests/education/test_task_router_parallel.py \
  tests/education/test_ce1_acg_integration.py
```

11 nouveaux cas d'intégration (dont 5 entrées invalides), plus 12 tests unitaires de stream. Les résultats ne sont pas déclarés avant exécution.

## Prochaine tranche
1. JWT apprenant / parent avec tenant et ownership vérifiés côté FastAPI.
2. API de session tutorée idempotente, sessions durables, version et anti-replay.
3. Décision pédagogique basée sur événements persistés, preuve autonome vérifiée serveur.
4. Adapters d'exécution réels et contrôlés (SymPy puis modèle général), suivi des coûts, logs sans secrets.
5. Brancher la classe CE1 par proxy Next.js protégé et tests E2E.
