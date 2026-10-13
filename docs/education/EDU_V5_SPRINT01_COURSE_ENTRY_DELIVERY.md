# RKJO Education V5 — Sprint 01: entrée pédagogique réelle
13 octobre 2026

## Besoin élève
Après avoir choisi une matière, l'apprenant doit accéder à un cours réel et savoir s'il existe des supports et des exercices. L'écran ne doit pas simuler une progression inexistante.

## Livré
- /education/courses lit GET /api/education/courses ; chargement, erreurs, zéro cours et catalogue réel.
- /education/courses/[courseId] lit la fiche du cours et ses évaluations depuis l'API ; présente la disponibilité des supports et questions.
- Le bouton d'accueil dirige vers le choix d'un cours au lieu de /education/session sans identifiants.
- Les indicateurs de démonstration de l'accueil sont clairement étiquetés ; la page Mes cours n'affiche plus le faux 64 %.

## Encore bloqué
- Pas encore de chapitre et prérequis explicites en modèle métier.
- Le détail des supports n'est pas encore un lecteur de chapitre.
- Les comptes individuels ne sont pas encore raccordés aux anciens proxies de QCM; aucun bypass de sécurité.
- La séance professeur IA contextualisée reste à réaliser au sprint suivant.

## Critères de recette
1. Avec un cours en base : sa matière, son niveau et ses supports s'affichent.
2. Sans cours : écran « Aucun cours disponible », aucun pourcentage inventé.
3. Avec au moins une évaluation : sa fiche apparaît, sans exposer les bonnes réponses.
4. API inaccessible : un message d'erreur lisible apparaît.
5. L'accueil dirige vers Mes cours.
6. Test manuel mobile Safari/Chrome et vérification accessibilité nécessaires.

## Vérifications sur Mac
```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-education-health
git pull --ff-only
PYTHONPATH=domains/education:platform/kernel:platform/api \
/Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m pytest -q tests/education/test_sprint01_course_navigation_contract.py
npm --prefix apps/web run lint
npm --prefix apps/web run build
```
Les tests statiques ne prouvent pas une séance complète. Il faut ouvrir http://localhost:3000/education/courses avec la vraie API Education démarrée, vérifier la liste et ouvrir une fiche de cours.
