# MM-RAG-03.2 — Dépôt OCR lié à un cours (backend sécurisé)

## Livré

Route opt-in `POST /rag/ocr/courses/{course_id}/documents` :
- Rôle opérateur minimum via middleware RKJO.
- `RKJO_RAG_OCR_API_ENABLED=true` requis, désactivé par défaut.
- Tenant obligatoire issu de l'identité authentifiée.
- Vérification du cours par `CourseService.get(tenant_id, course_id)`
  **avant** de démarrer le traitement OCR.
- PDF uniquement, signature vérifiée, taille bornée par le mécanisme d'upload.
- Identifiant du document `education-<uuid>` généré par le serveur.
- Réutilisation de l'OCR réel, de la préparation PII et de la publication pgvector.
- Association `CourseService.attach_document` uniquement après indexation réussie.
- Tests API de rôles, tenant, cours absent, format et liaison.

## Point de sécurité : interface Education

Le proxy web actuel `/api/rag/documents` et le proxy
`/api/education/courses/[courseId]/documents` reposent sur une clé API
opérateur **partagée** en serveur Next.js et n'effectuent pas de contrôle
utilisateur. Ils ne doivent pas servir de point d'entrée pour un dépôt OCR
utilisateur dans une interface exposée au public.

En conséquence, **aucune nouvelle route proxy web ou formulaire OCR public
n'est activé ici**. Le point d'intégration est préparé sur FastAPI ; le
prochain développement doit établir une session web et un jeton utilisateur
avec tenant et rôle, vérifiés par le backend.

Le dépôt et l'association au cours ne sont pas encore transactionnels
ensemble : si la liaison échoue après l'indexation, des chunks peuvent
rester orphelins. Ajouter une compensation/outbox avant production.

Un cours n'implique pas automatiquement l'autorisation de lecture par
un élève. L'endpoint `/rag/answer` interroge aujourd'hui le tenant ;
pour une vue apprenant, il faudra contrôler l'inscription, l'accès au
cours et les document_ids associés, puis restreindre la recherche à ce
périmètre précis, côté serveur.

## Vérification locale

```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-omnichannel
source /Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/activate
git pull --ff-only origin feat/v2-omnichannel-runtime-v1
export PYTHONPATH="$PWD/platform/kernel:$PWD/platform/api:$PWD/platform/worker:$PWD/domains/education:$PWD"

python3 -m pytest tests/api/test_education_ocr_course.py -v
python3 -m pytest tests/api/test_rag_strict_tenant.py -v
python3 -m pytest tests/api -q
python3 -m pytest tests/kernel/rag -q
git diff --check
git status --short
```

Ne pas confondre tests API simulés et recette complète FastAPI réelle
avec registre de cours et PostgreSQL : cette recette reste à ajouter.

## Sprint suivant

MM-RAG-03.3 : sessions web utilisateur, rôles enseignant/apprenant,
association de cours et documents vérifiée, proxy JWT par session,
puis interface de dépôt et questions/réponses avec pages.
