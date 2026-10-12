# RKJO Education — P0.2 pilote staging audio PostgreSQL
Date : 12/10/2026 | Branche : feat/edu-health-study-pipeline-v1

## Lot livré (streams D/E/F/S/B)
- Le pilote WAV conserve ses contrôles format, taille <= 50 MiB et durée réelle.
- API FastAPI opt-in `POST /education/study/stage-audio` : fichier WAV + formation/UE + droits confirmés, réponse avec `source_id`, durée, sha256, état `staged`.
- `GET /education/study/staged-audio/{source_id}` : métadonnées visibles seulement par le propriétaire.
- `DELETE /education/study/staged-audio/{source_id}` : suppression du contenu BYTEA et de la ligne propriétaire.
- Stockage transactionnel pilote : métadonnées + contenu BYTEA dans PostgreSQL, contrainte UNIQUE tenant/étudiant/formation/UE/hash, insertion idempotente et date d'expiration après 24 heures.
- Proxy Next.js à session pilote et formulaire : case optionnelle de sauvegarde temporaire ; le mode inspection d'origine reste sans stockage.
- Tests unitaires de contrôle local et tests d'intégration PostgreSQL isolés.

**Aucun worker ASR, aucune exécution de workflow, aucune transcription, aucun résumé, aucun débit.** La durée de rétention de 24 h n'est PAS une suppression automatique : exécuter `purge_expired()` depuis une tâche de maintenance dédiée avant tout usage réel.

## SÉCURITÉ / LIMITES EXPLICITES
Ce prototype **n'est pas un stockage prêt pour des données personnelles sensibles ou une production** : pas de chiffrement applicatif du fichier dans PostgreSQL, pas d'analyse antivirus, ni quota global, ni tâche automatique de purge. Ne pas importer d'audio contenant des données patient, ni d'enregistrements privés sensibles. Utiliser uniquement un environnement de test local, une base dédiée avec permissions restreintes et chiffrement disque configuré localement.

L'API ne doit PAS utiliser `RKJO_DATABASE_URL` pour ce lot. Elle exige `RKJO_EDUCATION_AUDIO_DATABASE_URL`, dédié, sans valeur par défaut. Éviter absolument la base principale RKJO (port 5432) et les autres bases métiers.

Le pilote est désactivé par défaut et requiert simultanément :
- `RKJO_EDUCATION_AUDIO_STAGING=enabled`
- `RKJO_AUDIO_STORAGE_ACK=local-postgres-only`
- `RKJO_EDUCATION_AUDIO_DATABASE_URL=<URL base PostgreSQL distincte>`
- connexion au backend depuis loopback, Bearer JWT étudiant tenant-bound ; Next.js tourne aussi en mode pilote local.

**Les secrets du pilote étudiant qui ont été affichés dans une conversation doivent être régénérés localement**. Ne jamais copier secrets, mot de passe ou URL contenant identifiants dans Git, les logs ou le chat. Redémarrer backend et frontend après rotation.

## Vérifications
```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-education-health
git pull --ff-only
PYTHONPATH=domains/education:platform/kernel:platform/api \
/Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m pytest -q \
  tests/education/test_study_audio_probe.py \
  tests/education/test_study_audio_staging.py \
  tests/education/test_study_audio_workflow.py \
  tests/education/test_study_audio_security.py \
  tests/education/test_study_media_intake.py
npm --prefix apps/web run lint
npm --prefix apps/web run build
```
Pour le test PostgreSQL facultatif, configurer `RKJO_EDUCATION_AUDIO_TEST_DATABASE_URL` vers une **base de test distincte et jetable uniquement**, puis exécuter `tests/education/test_study_audio_staging_postgres.py`. Sans variable, le test est ignoré. Tester deux imports identiques, lecture en tant qu'autre étudiant (404), suppression puis lecture (404). La vérification navigateur nécessite que les deux processus soient redémarrés.

## Prochaine tranche
- Adaptateur de stockage objet chiffré avec URL interne expirante + cycle de vie automatique.
- Quotas par propriétaire, validation MIME/codec sandboxée et analyse malveillante.
- Transaction outbox reliée à l'orchestration RKJO, retries bornés, DLQ, reprise et contrôle d'idempotence sous concurrence.
- Capability ASR avec transcript segments horodatés, revue humaine et artefacts sourcés.
- Devis et paiement uniquement après la mesure des coûts et la recette de la chaîne technique.

**Le lot ne doit pas être fusionné dans main avant la recette.**
