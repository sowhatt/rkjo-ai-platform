# MM-RAG-02.6 — Recette réelle OCR → API → pgvector → citations

## Livré

Test d'intégration `tests/api/test_rag_ocr_real_e2e_integration.py`.

- Création d'un PDF **rasterisé** synthétique en mémoire (Pillow).
- Appel `POST /rag/ocr/documents` avec les authentifications API existantes.
- Exécution des vrais binaires Poppler/Tesseract à travers `MixedPDFEvidenceExtractor`.
- Préparation des embeddings avec le moteur déterministe de test.
- Publication réelle dans une **table temporaire dédiée** de la base PostgreSQL de test,
  via `PostgresEvidencePublisher`. La table est supprimée en fin de test.
- Recherche HTTP `/rag/search` et vérification `tenant_id`, `page_number=1`,
  `extraction_method=ocr`.
- Réponse HTTP `/rag/answer` avec un générateur déterministe alimenté par le
  contexte récupéré. Vérification de `sources[].page_number=1`.
- Passage à un autre tenant : zéro résultat et refus de remplacer le document.

Le test ne sollicite **aucune API de modèle**. Il confirme la chaîne
technique, pas la qualité de génération d'un LLM en production.

## Prérequis Mac

- Poppler `pdftoppm` et Tesseract installés avec données `fra` et `eng`.
- Pillow dans le Python de RKJO (`python3 -m pip install Pillow` au besoin).
- PostgreSQL de test avec pgvector.
- Authentification factice configurée uniquement dans les fixtures API.

```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-omnichannel
source /Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/activate
git pull --ff-only origin feat/v2-omnichannel-runtime-v1
export PYTHONPATH="$PWD/platform/kernel:$PWD/platform/api:$PWD/platform/worker:$PWD/domains/education:$PWD"
export RKJO_TEST_DATABASE_URL="postgresql://rkjo:rkjo_password@localhost:5432/rkjo_multimodal_test"

python3 -m pytest tests/api/test_rag_ocr_real_e2e_integration.py -v -rs
python3 -m pytest tests/api/test_rag_ocr.py tests/api/test_rag_answer.py -q
python3 -m pytest tests/kernel/rag -q
git diff --check
git status --short
```

**Critère de succès :** la recette E2E affiche `PASSED`, jamais `SKIPPED`.
Les skips signalent une dépendance ou une base absente, pas une validation.

## Non couvert

- Qualité sémantique réelle d'un LLM (générateur de test déterministe).
- Données de santé personnelles ou OCR de pages complexes/tableaux.
- Publication applicative asynchrone via worker sandboxé.
- Workflow documentaire/versionning existant de la plateforme.
- Garantie de non-divulgation via identités anciennes non liées à un tenant :
  les routes historiques `/rag/search` et `/rag/answer` acceptent encore
  certaines identités non tenant-scopées. Ne **pas** activer le flag
  `RKJO_RAG_OCR_API_ENABLED` en production avant de corriger cette
  voie d'accès aux preuves OCR.
- Interface Education (livrable séparé après sécurisation des accès).

## Suites nécessaires avant mise en production

1. Forcer systématiquement le scope tenant pour les preuves OCR, même si
   un client utilise les routes RAG historiques.
2. Isoler les traitements PDF non fiables dans un worker à quotas CPU/mémoire.
3. Politique de confidentialité métier, antivirus, limitations d'usage,
   traçabilité de traitement et validation citations vs réponse.
