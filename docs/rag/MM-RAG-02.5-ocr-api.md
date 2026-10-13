# MM-RAG-02.5 — API OCR sécurisée (opt-in)

## Livré

- `POST /rag/ocr/documents` (multipart `file` PDF, `document_id` optionnel).
- Feature flag `RKJO_RAG_OCR_API_ENABLED=true` **désactivé par défaut**.
- Protection par le middleware RKJO : minimum rôle opérateur.
- Tenant impérativement issu d'une identité **authentifiée et liée à un tenant** ;
  toute identité sans tenant est refusée (403).
- Signature PDF `%PDF-`, extension PDF, limite 10 Mio via le téléversement existant,
  nettoyage du temporaire même en cas d'échec.
- Service `OCRIngestionService` : OCR réel → EvidenceDocument → nettoyage PII
  → embedding → `PostgresEvidencePublisher` atomique.
- `/rag/answer` expose `page_number` optionnel dans `sources`,
  tout en conservant la compatibilité des clients existants.
- Tests HTTP de sécurité et contrats (avec service OCR simulé).

## Attention avant activation en environnement partagé

**Ce jalon est expérimental et n'est pas une autorisation de traiter de vraies
données médicales personnelles.** Le sanitizer regex ne détecte pas tous les
identifiants et informations de santé. Activer seulement en recette sur PDF
synthétiques et base de test isolée. Le traitement est synchrone dans l'API,
donc non adapté à des volumes importants. Le processus OCR n'est pas isolé
dans un worker à quotas CPU/mémoire. Les PDF non fiables demandent des
protections supplémentaires (sandbox, antivirus, règles de conservation).

Les autres routes `/rag/search` et `/rag/answer` conservent leur
politique existante, qui peut accepter des identités sans tenant pour la
rétrocompatibilité. Pour interroger des preuves OCR, utiliser une
**identité liée à un tenant** et un filtre de document approprié.
Les premières versions OCR n'ont pas encore de métadonnées de version
dans le registre `rag_document_versions`.

## Validation Mac

```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-omnichannel
source /Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/activate
git pull --ff-only origin feat/v2-omnichannel-runtime-v1
export PYTHONPATH="$PWD/platform/kernel:$PWD/platform/api:$PWD/platform/worker:$PWD/domains/education:$PWD"
export RKJO_TEST_DATABASE_URL=postgresql://rkjo:rkjo_password@localhost:5432/rkjo_multimodal_test

python3 -m pytest tests/api/test_rag_ocr.py tests/api/test_rag_answer.py -v
python3 -m pytest tests/kernel/rag -q
python3 -m pytest tests/api/test_rag_documents.py tests/api/test_rag_answer.py -q
git diff --check
git status --short
```

Ne pas activer le feature flag pendant les tests unitaires ; ils le
configurent temporairement eux-mêmes. Contrôler les échecs avant d'avancer.

## Suites

- Vérifier les tenants non liés dans les tests d'API, PII métier étendue.
- Validation end-to-end API sur PDF synthétique réel + pgvector.
- Traitement asynchrone en worker isolé et policy de consommation.
- Interface Education pour téléverser et afficher les citations de pages.
