# RKJO Education — CE1 pilot pause HTTP (stream C/F)

Architecture fonctionnelle de l'utilisateur inchangée.

## Portée exacte
Cette branche livre une API FastAPI **pilote opt-in** et une base SQLite locale partagée entre requêtes HTTP du même serveur.
- JWT Bearer vérifié par le middleware API existant, UUID subject et tenant obligatoires.
- Refus des clés techniques et des identités dépourvues de sujet/tenant.
- Grant explicite tenant/professeur/élève.
- Le professeur ouvre une séance et peut PAUSE/RESUME/END avec version CAS.
- L'élève autorisé consulte l'état et soumet un événement /turns. Si la séance est en pause : HTTP 423 ; ancienne version : HTTP 409.
- /turns compte une tentative autorisée, **n'évalue pas** une réponse CE1 et ne remplace pas l'orchestrateur C.
- Aucune route Next.js/PWA n'est connectée dans cette branche.

## Sécurité et activation
DÉSACTIVÉ par défaut. Pour une recette locale isolée :
- `RKJO_EDU_CE1_PILOT_ENABLED=1`
- `RKJO_EDU_CE1_PILOT_DB=/chemin/absolu/ce1-pilot.sqlite3`
- `RKJO_EDU_CE1_PILOT_GRANTS='[{"tenant_id":"<uuid>","teacher_id":"<uuid>","learner_id":"<uuid>"}]'`

**Ne pas activer en production.** Les grants en variable d'environnement sont limités à une recette, non à un système de gestion d'établissement. Le service de JWT actuel doit réellement délivrer le tenant et les rôles corrects. L'affectation professeur doit être administrée de manière indépendante à terme. Le prototype ne gère ni persistance des contenus CE1, ni outbox, ni SSE/WebSocket, ni multi-worker PostgreSQL.

## Validation automatisée
```bash
PYTHONPATH=domains/education:platform/kernel:platform/api python -m pytest -q --tb=short \
 tests/education/test_ce1_pilot_http.py \
 tests/education/test_sqlite_session_store.py \
 tests/education/test_teacher_session_commands.py
```
Le test substitue uniquement le vérificateur de JWT à une identité de test pour isoler le contrat HTTP ; il ne teste pas la signature cryptographique JWT.

## Recette HTTP prévue
1. Authentifier un professeur au sein d'un tenant et un élève de la même affectation avec deux JWT distincts.
2. POST /education/ce1-sessions avec learner_id sur le JWT professeur.
3. GET /education/ce1-sessions/{session_id}/state avec JWT élève => active.
4. POST /education/ce1-sessions/{session_id}/commands avec PAUSE et expected_version:0 => paused v1.
5. GET state élève => paused; POST /turns => 423.
6. POST commands RESUME v1 => active v2; POST /turns v2 => accepté v3.
7. Tester un autre élève/tenant, une clé d'exploitation et un conflit de version => refus.

Le prochain stream B/T consommera ces endpoints après ajout d'une authentification PWA élève/professeur opérationnelle.
