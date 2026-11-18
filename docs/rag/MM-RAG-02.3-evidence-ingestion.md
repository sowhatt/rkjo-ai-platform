# MM-RAG-02.3 — Bridge OCR → RAG existant

## Livré (opt-in kernel, sans API publique)

`EvidenceRAGIngestion` accepte exclusivement `MixedPDFExtraction.complete`.
La méthode `prepare(..., tenant_id=...)` :

1. vérifie que le tenant autorisé correspond au tenant de la preuve ;
2. applique par défaut `RuleBasedPIISanitizer` avant tout embedding ;
3. fractionne **par EvidenceBlock/page**, sans traverser les pages ;
4. associe aux chunks le tenant, `evidence_document_id`, la page, la
   méthode d'extraction, la version de provenance et les contrôles PII ;
5. calcule les embeddings sur les contenus déjà nettoyés ;
6. renvoie une préparation sans écriture.

`ingest(..., tenant_id=...)` persiste ensuite ces chunks via le
`Retriever.vector_store` existant. Avec le store Postgres fourni dans RKJO,
les chunks utilisent la table `rag_chunks` et les métadonnées JSONB
existantes : **aucune migration DB nécessaire**.

Exemple d'utilisation interne :

```python
from rkjo_kernel.rag.evidence_ingestion import EvidenceRAGIngestion
from rkjo_kernel.rag.local_pdf_ocr import LocalTesseractPDFOCR
from rkjo_kernel.rag.multimodal_ocr import MixedPDFEvidenceExtractor

# retriever est le Retriever configuré de RKJO avec pgvector, dimensions
# et embedding-space correspondants, déjà initialisé par le service.
extracted = MixedPDFEvidenceExtractor(LocalTesseractPDFOCR()).extract(
    "/chemin/autorise/contrat.pdf",
    tenant_id=authenticated_tenant_id,
    document_id="contrat-2026",
)
bridge = EvidenceRAGIngestion(retriever=retriever)
prepared = bridge.prepare(extracted, tenant_id=authenticated_tenant_id)
# Seulement après autorisation et validation, écrire via stratégie atomique :
# bridge.ingest(extracted, tenant_id=authenticated_tenant_id)
filters = bridge.filters(
    tenant_id=authenticated_tenant_id, document_id="contrat-2026",
)
results = retriever.retrieve("Garantie optique ?", filters=filters)
# results[i].chunk.metadata["page_number"] préserve la citation de page.
```

## Réserves bloquantes avant l'activation production

- `VectorStore.add` écrit chunk par chunk, **pas transactionnel au niveau
  document**. Une interruption peut laisser un document incomplet visible.
  Il faut intégrer une stratégie de publication atomique/staging et
  d'idempotence via les composants document lifecycle existants.
- Le tenant doit être issu d'une identité authentifiée ; ne jamais faire
  confiance à un tenant transmis librement par un client.
- Les recherches doivent systématiquement passer un filtre tenant ;
  `Retriever.retrieve` ne l'impose pas tout seul.
- Le sanitizer actuel est à règles (email, téléphone, IBAN, IPv4) :
  ne détecte pas tous les noms, numéros de sécurité sociale, identifiants
  métier ou données de santé. Étendre la politique de confidentialité avant
  toute ingestion de documents réels sensibles.
- Le module de génération actuel retourne des références `chunk_id`
  et `document_id`, pas encore les **numéros de page en AnswerSource**.
  Ajouter ce champ et le contrôle des citations avant d'exposer une
  réponse `page 1` côté API.
- Les tests ci-dessous sont unitaires avec store mémoire, **pas une preuve
  d'écriture/lecture PostgreSQL réelle**.

## Validation sur Mac

```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-omnichannel
source /Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/activate
git pull --ff-only origin feat/v2-omnichannel-runtime-v1
export PYTHONPATH="$PWD/platform/kernel:$PWD/platform/api:$PWD/platform/worker:$PWD/domains/education:$PWD"
python3 -m pytest tests/kernel/rag/test_evidence_ingestion.py -v
python3 -m pytest tests/kernel/rag -q
python3 -m pytest tests/api/test_rag_documents.py tests/api/test_rag_answer.py -q
git diff --check
git status --short
```

## Prochain jalon

MM-RAG-02.4 : isolation et publication atomique PostgreSQL, citations de
page dans les sources de réponses, et test d'intégration sur un PDF scanné.
