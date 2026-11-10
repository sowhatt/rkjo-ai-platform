# MM-RAG-03.1 — Tenant obligatoire pour toutes les lectures RAG

## Problème corrigé

Les routes historiques `POST /rag/search` et `POST /rag/answer`
acceptaient une identité API authentifiée mais sans tenant configuré.
Dans ce cas, le filtre fourni par le client pouvait être conservé ou
absent, donnant un chemin de lecture non tenant-scopé vers `rag_chunks`,
qui contient aussi des preuves OCR.

## Changement

`bind_identity_tenant(..., require_tenant=True)` impose maintenant
que l'identité authentifiée porte un tenant non vide dans les deux
endpoints de lecture. L'absence de tenant provoque HTTP 403, sans
appeler les services de retrieval ni génération.

Le tenant du client reste comparé à celui de l'identité (403 en cas
de conflit), et un filtre tenant est injecté systématiquement.

La valeur par défaut de `bind_identity_tenant` reste
`require_tenant=False` pour ne pas modifier silencieusement
les flux historiques de gestion documentaire, hors lecture.

**Rupture de compatibilité intentionnelle** : toute clé API ou JWT sans
tenant ne peut plus appeler `/rag/search` ou `/rag/answer`. Configurer
`RKJO_VIEWER_TENANT_ID`, `RKJO_OPERATOR_TENANT_ID`,
`RKJO_ADMIN_TENANT_ID`, `RKJO_API_TENANT_ID` (selon la clé)
ou un JWT émis avec un tenant réellement autorisé.

## Validation Mac

```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-omnichannel
source /Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/activate
git pull --ff-only origin feat/v2-omnichannel-runtime-v1
export PYTHONPATH="$PWD/platform/kernel:$PWD/platform/api:$PWD/platform/worker:$PWD/domains/education:$PWD"

python3 -m pytest tests/api/test_rag_strict_tenant.py -v
python3 -m pytest tests/api -q
python3 -m pytest tests/kernel/rag -q
git diff --check
git status --short
```

Les tests de ce sprint ont été commités, **pas encore exécutés sur
le Mac de l'utilisateur**.

## Interface Education — blocage de sécurité

Le proxy Next.js actuel `apps/web/src/app/api/rag/documents/route.ts`
transmet une clé opérateur serveur, sans vérification d'une session utilisateur.
Ajouter simplement un bouton OCR utilisant ce proxy serait dangereux,
car il pourrait permettre des dépôts au nom du tenant serveur.

Avant d'exposer l'OCR dans Education :
1. Authentification et session utilisateur réelles au niveau Next.js.
2. Propagation au backend d'un jeton tenant-scopé par utilisateur, sans
   accepter un tenant arbitraire envoyé dans le navigateur.
3. Contrôle de rôle (enseignant/administrateur pour dépôt, droits de
   lecture élève) et liaison explicite document ↔ cours ↔ tenant.
4. Feature flag OCR maintenu off en production ; pas de données de santé
   avant contrôle PII métier/worker isolé.
5. Tests E2E d'accès professeur, élève et inter-tenant.

## Limites

Les routes de gestion documentaires historiques et les accès directs
au vector store doivent être audités séparément. Cette modification
ferme **la voie HTTP de lecture RAG**, pas l'ensemble de la
surface d'accès de la plateforme.
