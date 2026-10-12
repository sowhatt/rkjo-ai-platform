# RKJO Education — Streams B + D, incrément 1
Date : 13 octobre 2026 — Branche isolée : feat/edu-health-study-pipeline-v1

## Livré dans le code
- Extension de l'API existante `POST /education/study/preview-pdf` : elle fournit en plus `revision_notes` (extraits et références par page), `mind_map` (plan navigable regroupé par page), `generation_mode` et avertissement d'origine.
- Service pur `study_learning_views.py` : pas de fournisseur LLM, pas de données inventées, limite de 20 pages de texte affichées, références aux segments originaux.
- Interface `StudyPdfPreview.tsx` : onglets Fiches de révision, Carte des notions, Extraits du PDF ; consultation des branches par développement.
- Tests source, pages et limites dans `test_study_learning_views.py`.

## Ne pas confondre avec le produit final
La « fiche » actuelle est composée d'extraits ; elle n'est **pas encore** un résumé intelligent. La « carte des notions » est un plan interactif, **pas encore** un graphe sémantique. Les documents ne sont pas persistés ; la session reste un aperçu local sous contrôle d'identité. Pas de génération de flashcards, export, édition ni sauvegarde dans cet incrément.

## Recette
```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-education-health
git pull --ff-only
PYTHONPATH=domains/education:platform/kernel:platform/api \
/Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m pytest -q \
  tests/education/test_study_learning_views.py \
  tests/education/test_pdf_study_ingest.py \
  tests/education/test_study_documents_api.py \
  tests/education/test_study_preview_rbac.py
npm --prefix apps/web run lint
npm --prefix apps/web run build
```
Puis, avec le pilote local déjà configuré : `http://localhost:3000/education/study-tools` ; importer un PDF textuel **fictif** (sans données personnelles). Les PDF image sans couche texte exigent l'OCR qui n'est pas inclus ici.

## Suites des streams parallèles
- Stream D : segmentation concepts/sections (et non pages seulement), brancher le provider IA existant et contrôler citations et non-hallucination ; persistance/versionnement des artefacts.
- Stream B : vrai graphe de carte mentale navigable/éditable, fiche enrichie, export, bibliothèque de ressources et liens vers QCM.
- Stream T : comparaison avec un corpus pédagogique d'évaluation synthétique et validations fonctionnelles en navigateur.
