# MM-RAG-01 — Provenance multimodale et extraction PDF native

## Objectif

Étendre RKJO RAG **sans remplacer** l'ingestion texte existante et sans
confondre OCR avec analyse visuelle. Première livraison : contrats canoniques
réutilisables pour les futures étapes OCR, tableaux, images, audio et vidéo.

## Livré

- `rag/multimodal_evidence.py`: `EvidenceDocument`, `EvidenceBlock`,
  `EvidenceLocation`, méthodes d'extraction explicites.
- Provenance : tenant, document, bloc, page, coordonnées normalisées (xyxy),
  segment temporel, méthode native/OCR/VLM/ASR, référence opaque de l'asset.
- Citation autorisée seulement si le tenant demandé est celui du document.
- `rag/multimodal_pdf.py`: extraction du texte natif PDF *page par page*
  avec marqueur de méthode native, inspection des pages ne contenant pas
  de texte extractible et nécessitant l'OCR.
- Les images sans texte reconnu ne sont pas converties en faux chunks texte.
- Nouveaux tests de contrat, de provenance, de refus cross-tenant et de
  pages nécessitant OCR.

## Ce qui n'est PAS encore fait

- Ces contrats ne sont pas encore branchés sur `POST /rag/documents`.
  Ce dernier conserve son comportement textuel stable.
- Aucun OCR, VLM, extracteur de tableaux, stockage des images, embeddings
  multimodaux, indexation et recherche croisée, ni restitution graphique
  des citations n'est livré à cette étape.
- La simple présence d'une page contenant du texte n'assure pas que
  ses tableaux aient été compris. Leur analyse sera distincte.
- Les contrôles d'autorisation du futur stockage de références d'assets
  doivent être faits **au point de lecture**, pas uniquement dans le modèle.
- La durée de conservation, le chiffrement, l'audit, l'assainissement PII
  et les politiques tenant doivent être conservés dans le pipeline ultérieur.

## Exécution des tests

```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-omnichannel
source /Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/activate
git pull --ff-only origin feat/v2-omnichannel-runtime-v1
export PYTHONPATH="$PWD/platform/kernel:$PWD/platform/api:$PWD/platform/worker:$PWD/domains/education:$PWD"
python3 -m pytest tests/kernel/rag/test_multimodal_evidence.py -v
python3 -m pytest tests/kernel/rag -q
python3 -m pytest tests/api/test_rag_documents.py tests/api/test_rag_answer.py -q
git diff --check
git status --short
```

## Suite proposée

- **MM-RAG-02** — Adaptateur à l'OCR existant, modèle de sortie par page/bloc,
  tâches durables du Kernel multimodal, droits tenant de bout en bout.
- **MM-RAG-03** — Tables et figures avec références structurelles, stockage
  vérifiable et embeddings appropriés à chaque modalité.
- **MM-RAG-04** — Recherche hybride sur preuves, page/table/asset cités.
- **MM-RAG-05** — Évaluation de fidélité et coût/latence sur corpus assurance
  et Education, comparaison RAG texte vs multimodal.

Aucun merge vers main sans validation explicite.
