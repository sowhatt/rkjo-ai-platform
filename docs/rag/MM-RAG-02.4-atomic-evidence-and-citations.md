# MM-RAG-02.4 — Publication atomique et citations de pages

## Livré

- `PostgresEvidencePublisher.publish(PreparedEvidence, tenant_id=...)` effectue la
  suppression/remise des chunks d'un document dans une transaction PostgreSQL.
- `pg_advisory_xact_lock` sérialise les publications pour un même `document_id`.
- Refus d'écrire si le `document_id` existant est rattaché à un autre tenant.
- Validation tenant/document pour tous les chunks **avant** la connexion.
- Compatibilité table `rag_chunks`, JSONB et colonnes de provenance existantes.
- `AnswerSource.page_number` facultatif pour ne pas casser les réponses anciennes.
- `CitationContextBuilder` transmet la page au modèle de génération lorsque disponible.
- Tests d'intégration PostgreSQL : publication, remplacement, filtres tenant,
  collision inter-tenant, rollback lorsque la deuxième insertion échoue.
- Tests de citations de réponse.

## Séquence d'exécution interne (pas d'API publique activée)

```python
from rkjo_kernel.rag.evidence_ingestion import EvidenceRAGIngestion
from rkjo_kernel.rag.postgres_evidence_publisher import PostgresEvidencePublisher

bridge = EvidenceRAGIngestion(retriever=retriever)
prepared = bridge.prepare(extraction, tenant_id=authenticated_tenant_id)
publisher = PostgresEvidencePublisher(
    database_url=database_url,
    table_name=vector_store.table_name,
    embedding_space=embedding_space,
)
count = publisher.publish(prepared, tenant_id=authenticated_tenant_id)
filters = bridge.filters(
    tenant_id=authenticated_tenant_id, document_id=prepared.document_id,
)
# Toutes les recherches doivent recevoir ces filtres.
```

L'ancienne méthode `EvidenceRAGIngestion.ingest()` écrit chunk par chunk
et **ne garantit pas l'atomicité**. Utiliser le publisher pour PostgreSQL.

## Validation Mac

```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-omnichannel
source /Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/activate
git pull --ff-only origin feat/v2-omnichannel-runtime-v1
export PYTHONPATH="$PWD/platform/kernel:$PWD/platform/api:$PWD/platform/worker:$PWD/domains/education:$PWD"
export RKJO_TEST_DATABASE_URL=postgresql://rkjo:rkjo_password@localhost:5432/rkjo_multimodal_test
python3 -m pytest tests/kernel/rag/test_evidence_page_answer.py -v
python3 -m pytest tests/kernel/rag/test_postgres_evidence_publisher_integration.py -v -rs
python3 -m pytest tests/kernel/rag -q
python3 -m pytest tests/api/test_rag_documents.py tests/api/test_rag_answer.py -q
git diff --check
git status --short
```

ATTENTION : un test marqué SKIPPED faute de PostgreSQL accessible ne
constitue **pas** une validation d'intégration. Utiliser une DB de test
dédiée disposant de l'extension pgvector.

## Limites avant production

- Le code du publisher est un composant Kernel opt-in, **pas** une route
  API autorisée. Un service devra dériver le tenant de l'identité
  authentifiée et interdire les recherches sans filtre tenant.
- Les documents de santé personnels requièrent une politique de données
  sensibles plus robuste que le sanitizer regex actuel.
- Les identifiants de documents doivent être globalement uniques dans
  `rag_chunks` ; une collision entre tenants est refusée, non remappée.
- Les appels au store hérités hors du publisher peuvent contourner ses
  verrous : garantir que toutes les écritures OCR passent par le publisher.
- La transaction concerne `rag_chunks`, pas l'outbox ni le registre
  de versions de documents existant. Intégration transactionnelle à
  concevoir si ces composants sont raccordés.
- Le texte de réponse généré n'est pas automatiquement validé contre
  ses citations ; `page_number` reflète les métadonnées de retrieval.
- Un test complet **vrai OCR → PostgreSQL → API publique → réponse**
  reste à réaliser. Le test OCR réel précédent et les tests PostgreSQL
  sont séparés à ce stade.

## Prochain jalon

MM-RAG-02.5 : exposer ingestion/recherche via des endpoints autorisés,
politique de confidentialité renforcée, recherche tenant obligatoire
et recette intégrée sur PDF scanné réel.
