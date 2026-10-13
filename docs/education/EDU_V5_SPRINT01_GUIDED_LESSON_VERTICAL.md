# RKJO Education — Sprint 01, séquence pédagogique guidée

13 octobre 2026 — branche feat/edu-health-study-pipeline-v1

## Ce qui est livré
- La fiche de cours affiche maintenant une activité guidée lorsque l'API retourne au moins une question d'évaluation.
- Les questions proviennent de GET /education/courses/{id}/assessments, pas de données de démonstration.
- Objectif de compréhension fondé sur le competency_code lorsqu'il existe ; en son absence, objectif générique.
- Séquence locale : conseil méthodologique → réponse libre → autoévaluation réflexive → question suivante.
- Pas de note, pas de correction automatique et pas de mise à jour de maîtrise prétendue.
- État sans évaluation : la leçon guidée ne s'affiche pas.
- L'état de la séquence n'est pas persisté : rafraîchir la page recommence l'exercice.

## Non réalisé
La séance ne produit pas encore de leçon explicative générée à partir des documents ; elle ne détecte pas l'exactitude d'une réponse. Le service tutor existant a besoin d'un learner UUID authentifié et d'un course UUID associé : la fiche de cours générique n'en dispose pas encore. Aucune clé opérateur ni identité forgée côté navigateur ne doit combler ce manque.

## Recette utilisateur
1. Ouvrir /education/courses puis un cours contenant une évaluation.
2. Constater que l'activité prend la question réelle du cours.
3. Cliquer « Je réponds », remplir une réponse, puis compléter la réflexion.
4. Naviguer à la question suivante ; vérifier la remise à zéro du formulaire.
5. Tester une autre matière et un cours sans évaluations.
6. Ne pas considérer cette séquence comme une validation de maîtrise ou le professeur IA final.

## Vérifications
```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-education-health
git pull --ff-only
PYTHONPATH=domains/education:platform/kernel:platform/api \
/Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m pytest -q \
 tests/education/test_sprint01_course_navigation_contract.py \
 tests/education/test_guided_learning_ui_contract.py
npm --prefix apps/web run lint
npm --prefix apps/web run build
```
