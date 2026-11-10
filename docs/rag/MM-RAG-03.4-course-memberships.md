# MM-RAG-03.4 — Inscriptions pédagogiques

Ce jalon introduit un référentiel PostgreSQL de membres par cours et tenant, avec rôles `teacher` et `learner`, séparés des rôles techniques de transport API.

Nouvelles routes :
- `POST /education/courses/{course_id}/members` : inscription par un administrateur API **nommément identifié** et rattaché à un tenant. L'opération vérifie d'abord l'existence du cours dans ce tenant.
- `POST /education/courses/{course_id}/learner-answer` : recherche documentaire accessible avec rôle API `viewer` uniquement si le `subject` JWT est réellement inscrit dans ce cours, et si le document est lié au cours. Les filtres `tenant_id` et `evidence_document_id` sont imposés côté serveur.

La table `education_course_memberships` possède une clé primaire (tenant, cours, subject), une contrainte de rôle, et une clé étrangère vers `education_courses`. Sa création est automatique dans la dépendance du service d'accès.

## Vérification locale

```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-omnichannel
source /Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/activate
git pull --ff-only origin feat/v2-omnichannel-runtime-v1
export PYTHONPATH="$PWD/platform/kernel:$PWD/platform/api:$PWD/platform/worker:$PWD/domains/education:$PWD"
python3 -m pytest tests/api/test_education_course_memberships.py -v
python3 -m pytest tests/api -q
python3 -m pytest tests/kernel/rag -q
git diff --check
git status --short
```

## Limites importantes

Les tests API utilisent un dépôt d'inscriptions simulé ; une recette PostgreSQL réelle sera nécessaire. Le rôle technique opérateur des anciennes routes Education ne prouve pas la propriété du cours. Les routes historiques d'accès aux cours et de dépôt doivent également être soumises aux règles pédagogiques avant ouverture aux utilisateurs finaux.

La couche Next.js n'a pas encore de session utilisateur vérifiée : aucune interface publique de dépôt ou d'inscription n'est activée. Les clés API côté serveur ne doivent pas servir d'identité personnelle.

Le modèle ne comprend pas encore les invitations, l'expiration/révocation de l'inscription, les propriétaires de cours, la journalisation d'audit, les protections anti-abus et la gestion transactionnelle entre OCR, indexation et rattachement au cours. Aucun merge vers main ni déploiement n'a été effectué.
