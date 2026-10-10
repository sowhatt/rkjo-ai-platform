# RKJO Education — Classe CE1 interactive V1

## Portée
Démonstration locale et scénarisée : explication du passage par 10, dialogue enseignant/élève simulé, tableau de jetons, brouillon, entraînement avec trois indices maximum, nouvelle question de preuve sans indice, bilan avec tentatives et recommandation. Aucun modèle IA, microphone, stockage ou API privée n'est utilisé. Les exercices sont fixes. Cette livraison ne remplace pas les mécanismes de preuve et de maîtrise du backend.

## Validation technique
```bash
npm --prefix apps/web ci
npm --prefix apps/web run lint
npm --prefix apps/web run build
npm --prefix apps/web audit --omit=dev
npm --prefix apps/web run dev -- --port 3001
```
Ouvrir http://localhost:3001/education/classe-ce1.

## Recette fonctionnelle
1. L'écran montre le calcul 8 + 5 et la méthode 8 + 2 = 10, 10 + 3 = 13.
2. Démarrer l'exercice ; saisir une réponse invalide : refus avec explication et sans passage à l'étape suivante.
3. Saisir 12 : le professeur invite à réessayer ; l'étape reste entraînement.
4. Demander un indice : le compteur augmente et le tableau révèle la méthode ; au maximum trois indices.
5. Saisir 13 : passage à une nouvelle question 7 + 6 sans indice.
6. Vérifier l'absence du bouton indice et de la décomposition pendant la preuve.
7. Saisir 12 : bilan de révision, pas d'attribution de maîtrise.
8. Recommencer ; terminer par 13 à l'étape autonome : bilan réussite.
9. Tester navigation clavier, smartphone et trois tailles d'écran.
10. Vérifier que ni voix ni progression persistante ne sont annoncées comme fonctionnelles.

## Limites et prochains contrats d'intégration
- Stream A : service tutoriel dynamique avec explications adaptées.
- Stream C : preuves persistantes, maîtrise, prérequis et NBA ; ne jamais assimiler une réussite guidée à une preuve autonome.
- Stream G : sélection et exécution réelle des modèles, métriques de routage.
- Stream E : tableau blanc dessiné et audio après gestion explicite des permissions.
- Stream F : vérification JWT, tenant/learner grants et protection des routes avant tout stockage.
