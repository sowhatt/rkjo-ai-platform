# MM-RAG-02 — Extraction PDF mixte et adaptateur OCR

## Livré

- `rkjo_kernel.rag.multimodal_ocr.PDFPageOCRPort` :
  interface du fournisseur OCR pour **une page PDF**. Aucun SDK OCR imposé.
- `OCRPageResult` : identifiants tenant/document/page, texte et confiance
  facultative vérifiée dans [0, 1].
- `MixedPDFEvidenceExtractor` : text natif via pypdf, OCR **uniquement**
  pour les pages sans texte natif, page d'origine conservée dans
  `EvidenceBlock` avec `ExtractionMethod.OCR`.
- Résultat `MixedPDFExtraction` : pages OCR, pages rejetées, booléen
  `complete`. Tout OCR vide ou provenance incohérente échoue par défaut.
- Quotas : maximum 100 pages, 100 000 caractères/page par défaut.
- Aucun changement de `/rag/documents` : l'ingestion RAG de production
  reste stable et **n'indexe pas** ces résultats non encore approuvés.

## Limites importantes

La branche inspectée contient un Kernel multimodal de gestion de jobs,
mais **aucun adaptateur OCR exécutable** n'a été identifié. Ce sprint
construit une interface injectable, pas un moteur OCR opérationnel.
L'adaptateur réel doit convertir une page PDF en image de manière bornée,
appliquer une politique de tenant, gérer les secrets et quotas,
et retourner les résultats sous `OCRPageResult`.

L'extraction native sur une page n'équivaut pas à un contrôle de sa mise
en page. Une image ou un tableau présent sur une page contenant déjà du
texte peut rester non compris. Ce sera traité dans une étape layout/table.

Les résultats de ce module **ne doivent pas être enregistrés dans les
embeddings** sans pipeline préalable de nettoyage PII, validation
d'autorisation tenant au point d'écriture, vérification qualité OCR et
validation de complétude. L'option `allow_incomplete=True` sert
à la revue diagnostique, pas à rendre des preuves partielles interrogeables.

Le traitement est synchrone dans ce composant pur. Pour les fichiers
volumineux, la future orchestration réutilisera les jobs durables du Kernel
multimodal (retries, DLQ, idempotence), avec isolation des tenants.

## Exemple d'injection

```python
from pathlib import Path
from rkjo_kernel.rag.multimodal_ocr import (
    MixedPDFEvidenceExtractor, OCRPageResult,
)

class AuthorizedOCR:
    def recognize_page(self, *, pdf_path: Path, tenant_id: str,
                       document_id: str, page_number: int) -> OCRPageResult:
        # TODO: rasteriser uniquement cette page et appeler le fournisseur
        # OCR autorisé, sans exposer les données entre tenants.
        raise NotImplementedError("Configure a real OCR adapter.")

extractor = MixedPDFEvidenceExtractor(AuthorizedOCR())
# extractor.extract("/tmp/contract.pdf", tenant_id="a", document_id="c1")
```

## Validation Mac

```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-omnichannel
source /Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/activate
git pull --ff-only origin feat/v2-omnichannel-runtime-v1
export PYTHONPATH="$PWD/platform/kernel:$PWD/platform/api:$PWD/platform/worker:$PWD/domains/education:$PWD"
python3 -m pytest tests/kernel/rag/test_multimodal_ocr.py -v
python3 -m pytest tests/kernel/rag -q
python3 -m pytest tests/api/test_rag_documents.py tests/api/test_rag_answer.py -q
git diff --check
git status --short
```

## Suite MM-RAG-02.2

1. Choisir et implémenter un véritable fournisseur OCR (local ou distant).
2. Traitement borné page-par-page avec classification de confidentialité.
3. Jobs durables et reprise, idempotence, tenant authorization à chaque transition.
4. Validation OCR et PII avant écriture atomique, métadonnées de provenance
   jusqu'à `rag_chunks`.
5. Test d'intégration réel sur PDF mixte, scanné, tableau et contrat d'assurance.
