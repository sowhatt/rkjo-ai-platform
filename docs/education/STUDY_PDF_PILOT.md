# RKJO Education — pilote PDF dans l'interface étudiant

## Objectif
Page `/education/study-tools` : choisir médecine, pharmacie ou soins infirmiers, une UE, un document CM/TD/TP, puis prévisualiser les extraits PDF avec les numéros de pages.

Le document n'est pas persisté. Cette fonction n'est PAS une génération de fiches IA, de flashcards ni d'examens.

## Configuration locale

Dans le worktree Education, lancer l'API avec l'environnement Python disponible :

```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-education-health
PYTHONPATH=domains/education:platform/kernel:platform/api /Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m uvicorn rkjo_api.main:app --host 127.0.0.1 --port 8020
```

Dans un second terminal, lancer Next.js :

```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-education-health
cd apps/web
RKJO_EDUCATION_STUDY_PILOT=enabled RKJO_EDUCATION_API_URL=http://127.0.0.1:8020 npm run dev
```

Ouvrir `http://localhost:3000/education/study-tools`.

**Authentification du pilote :** la route FastAPI exige un JWT Bearer de test valide, signé par la configuration locale RKJO, avec un `subject` et un `tenant` ; les seules clés API RKJO ne suffisent pas. Ne jamais utiliser des jetons de production dans ce formulaire de démonstration. Le jeton est fourni au navigateur pour ce pilote uniquement, n'est pas conservé dans le stockage navigateur, et est effacé après chaque tentative.

**Production :** intégrer les sessions serveur sécurisées avant activation publique, ajouter antivirus/limites d'abus, consentement/licences pour supports universitaires, stockage chiffré isolé par tenant et mécanismes d'expiration/suppression. Ne pas déployer ce pilote comme solution de production.

## Vérifications

```bash
npm --prefix apps/web run lint
npm --prefix apps/web run build
PYTHONPATH=domains/education:platform/kernel:platform/api /Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m pytest -q tests/education
```

Pour un vrai parcours manuel : faire le test avec un PDF texte autorisé et un jeton de test ; vérifier l'affichage des pages ; refaire sans jeton (refus 401/403) puis avec un PDF scanné (422 OCR requis). Aucun fournisseur IA externe n'est appelé par cette route.
