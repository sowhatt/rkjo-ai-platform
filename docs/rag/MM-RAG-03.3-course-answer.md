# MM-RAG-03.3 — Réponse RAG limitée au cours

La route `POST /education/courses/{course_id}/answer` exige un opérateur authentifié avec tenant. Le document demandé doit être lié au cours dans `CourseService`. La recherche filtre simultanément `tenant_id` et `evidence_document_id` et retourne les sources avec leur page.

La fonctionnalité reste côté backend. La vue élève nécessite encore une gestion des inscriptions et des sessions utilisateur web. Le rôle technique opérateur n'établit pas à lui seul la propriété pédagogique du cours.

Validation locale :

```bash
python3 -m pytest tests/api/test_education_course_answer_scope.py -v
python3 -m pytest tests/api -q
python3 -m pytest tests/kernel/rag -q
```

Ne pas publier de proxy Next.js à clé serveur partagée comme accès utilisateur. Aucune activation production ni merge vers main.
