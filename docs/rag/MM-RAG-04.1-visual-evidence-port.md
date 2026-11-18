# MM-RAG-04.1 — Port d'analyse visuelle générique (Kernel)

## Livré
- `rag/visual_evidence.py`: `VisualRegion`, `VisualResult`, `VisualAnalysisPort`, `VisualEvidenceExtractor`.
- Région IMAGE ou TABLE avec page et coordonnées normalisées, identifiant d'asset opaque.
- Enrichissement *opt-in* d'un `EvidenceDocument` sans changer les blocs OCR/natifs.
- Validation stricte du tenant, document, bloc, asset, type, page et bounding box **après** retour de l'adaptateur.
- Refus des résultats vides, trop longs et des identifiants dupliqués.
- Les blocs VLM portent un texte explicite et deviennent recherchables par le moteur textuel existant. La citation garde page, zone et asset.

## Non livré
- Pas de fournisseur VLM intégré, pas de récupération d'images, pas de stockage d'assets ni d'API publique.
- Pas de compréhension garantie des cellules de tableaux, ni de recherche vectorielle image-native.
- Aucun lien automatique avec le pipeline OCR ou la publication atomique : un orchestrateur autorisé reste à construire.
- Les descriptions de modèle ne sont pas des faits vérifiés : conserver un contrôle qualité humain/documentaire.
- Les résultats doivent être assainis avant embeddings avec le pipeline PII existant.

## Contrat sécurité
- L'appelant autorise le tenant et résout l'asset par une couche sécurisée; **ne jamais** accepter une URL arbitraire de l'utilisateur.
- L'adaptateur doit appliquer quotas et restrictions réseau, temps, mémoire et payload.
- Les régions doivent être issues d'un repérage fiable (PDF renderer, détecteur contrôlé, sélection humaine), non inventées par le LLM.
- En cas d'échec d'une région, aucun `EvidenceDocument` enrichi n'est renvoyé.

## Vérification
```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-omnichannel
source /Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/activate
git pull --ff-only origin feat/v2-omnichannel-runtime-v1
export PYTHONPATH="$PWD/platform/kernel:$PWD/platform/api:$PWD/platform/worker:$PWD/domains/education:$PWD"
python3 -m pytest tests/kernel/rag/test_visual_evidence.py -v
python3 -m pytest tests/kernel/rag tests/api -q
git diff --check
git status --short
```

## Étape suivante
MM-RAG-04.2 : resolver d'assets tenant-scopé, adaptateur VLM concret, ingestion orchestrée sûre, évaluation tableaux/figures et intégration à la publication atomique.
