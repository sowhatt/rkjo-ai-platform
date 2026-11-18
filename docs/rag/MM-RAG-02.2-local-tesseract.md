# MM-RAG-02.2 — Fournisseur OCR local Poppler/Tesseract

## Livré
- `LocalTesseractPDFOCR`, adaptateur concret du `PDFPageOCRPort`.
- Conversion **d'une seule page** via `pdftoppm` (Poppler), PNG limité à 1800 px de dimension maximale par défaut.
- Reconnaissance via `tesseract` (par défaut `fra+eng`).
- Sous-processus sans shell ; stdin/stdout/stderr supprimés pour limiter les fuites de données sensibles dans les journaux.
- Répertoire temporaire privé effacé automatiquement ; fichiers PDF conservés hors du répertoire temporaire (responsabilité du service appelant).
- Validation des entrées ; limites PDF 20 MiB, image 20 MiB, texte 100 000 caractères, délai 30 secondes **par commande** (valeurs configurables).
- Renvoi de `OCRPageResult` avec `tenant_id`, `document_id`, numéro de page ; confiance `None` (pas de fausse mesure).
- Tests unitaires simulés du rendu, de la reconnaissance, des limites, de l'expiration, du nettoyage et du PDF mixte.

## Installation sur Mac (locale)

```bash
brew install poppler tesseract tesseract-lang
which pdftoppm
which tesseract
tesseract --list-langs
```

Vérifier que **fra** et **eng** sont disponibles ; sinon installer les données linguistiques nécessaires. Aucune dépendance Python supplémentaire.

## Validation

```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-omnichannel
source /Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/activate
git pull --ff-only origin feat/v2-omnichannel-runtime-v1
export PYTHONPATH="$PWD/platform/kernel:$PWD/platform/api:$PWD/platform/worker:$PWD/domains/education:$PWD"
python3 -m pytest tests/kernel/rag/test_local_pdf_ocr.py tests/kernel/rag/test_multimodal_ocr.py -v
python3 -m pytest tests/kernel/rag -q
python3 -m pytest tests/api/test_rag_documents.py tests/api/test_rag_answer.py -q
git diff --check
git status --short
```

### Test de reconnaissance réel sur un PDF scanné **non sensible**

```bash
python3 - <<'PY'
from pathlib import Path
from rkjo_kernel.rag.local_pdf_ocr import LocalTesseractPDFOCR

pdf = Path("/CHEMIN/VERS/DOCUMENT_TEST_SCANNE.pdf")
result = LocalTesseractPDFOCR().recognize_page(
    pdf_path=pdf, tenant_id="tenant-test",
    document_id="document-test", page_number=1,
)
print("page:", result.page_number, "caractères:", len(result.text))
print("extrait:", result.text[:200])
PY
```

## Limites et sécurité

- **Pas encore branché** sur `POST /rag/documents`, aucun chunk indexé ; pas de changement au flux production.
- Il faut authentifier l'accès au PDF par tenant **avant** d'invoquer cet adaptateur. Ce module ne lit ni JWT ni base d'autorisations.
- L'OCR effectue uniquement une reconnaissance de caractères, **sans extraction structurée de tableaux**.
- Le texte OCR doit passer par la sanitization PII, les contrôles de complétude et une validation de provenance avant indexation.
- La taille d'image et le temps d'exécution sont bornés, mais les PDF non fiables devraient être traités dans des workers isolés et limités en CPU/mémoire ; `subprocess.run` ne constitue pas un sandbox.
- Sur les pages contenant un peu de texte natif, l'extracteur mixte ne tente pas d'OCR de toutes les images ; une phase Layout/VLM sera nécessaire.
- Aucun test d'exécution sur de vrais PDF, ni sur les binaires locaux de l'utilisateur, n'a été réalisé par l'assistant.

## Étape suivante

MM-RAG-02.3 : intégrer l'extraction via une orchestration asynchrone isolée par tenant, puis ajout de contrôles qualité, PII et provenance lors de l'indexation ; tests d'intégration sur vrais PDF scannés et mixtes.
