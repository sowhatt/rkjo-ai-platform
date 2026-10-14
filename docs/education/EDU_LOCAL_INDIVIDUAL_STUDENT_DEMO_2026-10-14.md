# RKJO Education — Démonstration locale avec identité individuelle
Date : 14 octobre 2026
Branche : feat/edu-health-study-pipeline-v1

## Périmètre
La fiche de cours peut désormais connecter un élève de démonstration distinct de la session pilote PDF partagée. Une session HTTP-only est émise par Next.js, et une requête de feedback est transmise à FastAPI avec un JWT court (60 s) dont le sujet est l'UUID de l'élève configuré côté serveur. Le navigateur ne reçoit jamais ce JWT ni la clé de signature.

Il s'agit d'un **compte individuel de démonstration préconfiguré**, pas d'un système de création de comptes ni d'une authentification de production. Il ne faut pas activer ce mécanisme sur Railway ou un serveur accessible au public. Un seul élève est supporté dans cette version locale et le mot de passe de démo est en variable d'environnement.

## Prérequis importants
- Environnement Next.js en développement et accès depuis localhost ou 127.0.0.1.
- API FastAPI locale démarrée et connectée à PostgreSQL.
- Un vrai `tenant_id` UUID et un vrai `learner_id` UUID créés dans **ce même tenant** de la base.
- Un cours UUID avec évaluation et questions, visible sur /education/courses.
- Les documents indexés dans le RAG doivent être associés au cours, sinon la réponse ne peut pas être considérée comme vérifiée par les sources.
- La **même** valeur RKJO_JWT_SECRET (32 caractères minimum recommandés) côté Next.js et FastAPI.
- La configuration d'accès en lecture au catalogue reste inchangée.

## Variables uniquement sur le poste local
Exemple de noms de variables dans apps/web/.env.local (remplacer les valeurs soi-même, ne jamais committer ce fichier) :
```bash
RKJO_EDUCATION_INDIVIDUAL_DEMO=enabled
RKJO_EDUCATION_STUDENT_ID=<UUID de l'apprenant existant>
RKJO_EDUCATION_STUDENT_TENANT_ID=<UUID du tenant réel>
RKJO_EDUCATION_STUDENT_PASSWORD=<code local réservé à cet apprenant>
RKJO_EDUCATION_STUDENT_SESSION_SECRET=<secret aléatoire d'au moins 32 caractères>
RKJO_JWT_SECRET=<même secret que le FastAPI local>
RKJO_EDUCATION_API_URL=http://127.0.0.1:8000
```
Ne jamais renseigner un identifiant inexistant ou un UUID inventé. Le serveur FastAPI doit posséder ce dossier apprenant dans PostgreSQL.

## Recette manuelle
1. Redémarrer Next.js après modification des variables.
2. Ouvrir /education/courses, sélectionner un cours avec une évaluation.
3. Avancer jusqu'à l'étape de réflexion.
4. Saisir le code individuel configuré et cliquer « Connexion étudiant ».
5. Cliquer « Demander un retour au professeur IA ».
6. Vérifier la réponse formative et les sources accessibles. En cas de documents RAG manquants, la réponse ne doit pas être interprétée comme une correction vérifiée.
7. Cliquer « Se déconnecter », vérifier que l'accès ne fonctionne plus.
8. Vérifier que l'ancienne session pilote partagée obtient 403 et qu'aucune session obtient 401.
9. Vérifier que l'API FastAPI rejette les cours/questions appartenant à un autre tenant.

## Limitations et sécurité
- Ne fournit pas un répertoire d'élèves, ni une gestion de multiples mots de passe, ni un fournisseur OIDC.
- L'accès au cours et aux évaluations demeure le circuit préexistant ; le nouveau mécanisme ne change que les retours du tuteur.
- La sortie du modèle est formative : `graded=false`, `mastery_updated=false`.
- Le projet a besoin d'une vraie authentification étudiante multisession (OIDC ou autre) avec mappage de compte vers learner_id et vérification d'inscription au cours.
- Il faut exécuter les tests et une recette en navigateur avant toute validation de sprint.
- Les prompts sont des données de l'élève : le RAG reste filtré par tenant et documents, mais les réponses LLM doivent être traitées comme non garanties.

## Validation du code
```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-education-health
git pull --ff-only
PYTHONPATH=domains/education:platform/kernel:platform/api \
/Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m pytest -q \
 tests/education/test_guided_learning_ui_contract.py \
 tests/education/test_tutor_formative_feedback.py
npm --prefix apps/web run lint
npm --prefix apps/web run build
```
