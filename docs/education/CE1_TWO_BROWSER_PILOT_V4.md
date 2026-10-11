# RKJO Education — recette à deux navigateurs, V4

**Schéma d'architecture utilisateur inchangé.** Branche de raccordement pilote B/T + C/F. Pas de fusion main ni de déploiement production.

## Ce qui est livré
- API pilote FastAPI V3 : professeur crée/pause/reprend/termine; élève consulte et soumet une activité test (sans correction).
- V4 : GET /education/ce1-sessions/{uuid}/teacher-state, strictement réservé au professeur assigné.
- Page professeur : /education/pilote-ce1/professeur
- Page élève : /education/pilote-ce1/eleve
- Synchronisation par interrogation toutes les deux secondes.
- Un relais Next.js /api/ce1-pilot/... vers FastAPI, seulement en mode développement ET RKJO_CE1_PILOT_WEB_ENABLED=1, vers une API HTTP localhost, sans clé serveur et sans cookie.
- Les JWT sont saisis localement et conservés uniquement dans l'état React : **ne pas utiliser de véritables comptes d'enfants**.

## Préconditions et sécurité
Les jetons individuels doivent être distincts (teacher / learner), signés et comporter un sujet UUID et tenant UUID. Le rôle professeur est OPERATOR (pour le pilote uniquement), le rôle élève VIEWER. Les grants professeur/élève sont préconfigurés par environnement. Il ne s'agit PAS d'un vrai fournisseur d'identité scolaire.

Le relais local est désactivé hors `NODE_ENV=development`. Ne pas déployer sur Railway et ne pas y mettre de vrais JWT ou données élèves. Ni cache partagé ni localStorage de jeton.

## Tests automatisés (sans activation du pilote)
```bash
PYTHONPATH=domains/education:platform/kernel:platform/api python -m pytest -q --tb=short \
 tests/education/test_ce1_pilot_http.py \
 tests/education/test_sqlite_session_store.py \
 tests/education/test_teacher_session_commands.py
npm --prefix apps/web ci
npm --prefix apps/web run lint
npm --prefix apps/web run build
```

## Préparer uniquement une recette locale
Dans un terminal (remplacer les UUID par ceux générés localement, aucun compte réel) :
```bash
export RKJO_JWT_SECRET="CHANGE_ME_RANDOM_LOCAL_ONLY"
export RKJO_EDU_CE1_PILOT_ENABLED=1
export RKJO_EDU_CE1_PILOT_DB=/tmp/rkjo-ce1-pilot-v4.sqlite3
export RKJO_EDU_CE1_PILOT_GRANTS='[{"tenant_id":"UUID_TENANT","teacher_id":"UUID_TEACHER","learner_id":"UUID_LEARNER"}]'
PYTHONPATH=domains/education:platform/kernel:platform/api uvicorn rkjo_api.main:app --host 127.0.0.1 --port 8000
```
Dans un deuxième terminal :
```bash
RKJO_CE1_PILOT_WEB_ENABLED=1 RKJO_CE1_PILOT_API_URL=http://127.0.0.1:8000 \
npm --prefix apps/web run dev -- --port 3004
```
Produire deux JWT de recette avec `rkjo_api.jwt_auth.create_access_token` (subject teacher UUID / OPERATOR et subject learner UUID / VIEWER, même tenant UUID). Ils doivent être saisis chacun dans **leur propre** navigateur et ne pas être échangés.

1. Sur :3004/education/pilote-ce1/professeur, saisir JWT professeur, UUID élève fictif, puis Créer une séance.
2. Copier uniquement le session_id dans :3004/education/pilote-ce1/eleve, saisir JWT élève, puis Connecter et synchroniser.
3. Professeur clique Pause. Élève voit En pause sous 2 s ; Envoyer une activité est désactivé.
4. Essayer quand même POST /turns directement avec JWT élève : HTTP 423.
5. Professeur clique Reprendre ; l'élève voit Active ; une activité test est acceptée avec version courante.
6. Tester une mauvaise affectation et une ancienne version : 403 et 409.

## Limites de cette livraison
- Pas de correction réelle par C, pas d'IA ni d'ardoise connectée à cette séance.
- Pas d'authentification scolaire ni de gestion durable des affectations; clé de signature locale de recette.
- SQLite, pas PostgreSQL ; pas de tests multi-worker / multi-instance.
- Pas de push SSE (polling 2 s uniquement), donc l'interface ne se met pas à jour instantanément.
- Le bouton d'activité envoie un événement de contrôle de version, **pas une réponse scolaire**.
- La supervision réelle S/T et l'intégration avec EducationCe1Classroom V2 restent distinctes.

## Jalon suivant
Brancher l'interface de classe CE1 V2 au contrôle de séance sans autoriser de correction si le serveur refuse l'action; puis remplacer les grants de recette par un vrai service d'affectation.
