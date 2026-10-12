# RKJO Education — P0.2 : workflow audio, premier incrément
Date : 12 octobre 2026 | Branche : feat/edu-health-study-pipeline-v1

## Livré en code
- Correction RBAC : `POST /education/study/inspect-audio` est autorisé au rôle étudiant `VIEWER`, tandis que les autres écritures Education gardent la règle `OPERATOR`. L'endpoint requiert en outre un JWT individuel lié à un tenant.
- Contrat `AudioWorkflowAdmission` : propriétaire, source versionnée, empreinte SHA-256, référence de stockage privée, vérification de l'autorisation et du paiement le cas échéant.
- Clé d'idempotence calculée à partir du tenant, de l'étudiant, de la source, de la version, du contenu et de l'opération ; identifiant d'exécution déterministe.
- `build_audio_transcription_workflow` construit une définition native `WorkflowDefinition` et des `WorkflowStep` du kernel existant, pour les capacités `education.audio.transcribe` et `education.audio.review`.
- Tests pour admissions refusées, identité et version différentes, construction du workflow et règle RBAC.

## Non livré — ne pas assimiler la définition à un job actif
**Aucun stockage audio, aucun dispatch, aucune capacité ASR enregistrée, aucun worker, aucune transcription et aucun débit ne sont activés par ce commit.** L'URL `private://` est ici un contrat de référence, pas un stockage effectivement implémenté. La création d'un job persistant doit venir après stockage privé effectif et conditions commerciales satisfaites. Les fonctions de démonstration actuelles restent découplées des paiements.

## Ordre du prochain lot
1. Choisir l'adaptateur de stockage privé déjà utilisé par RKJO, ou en définir un clairement limité, avec suppression/rétention, quotas et chiffrement.
2. Ajouter l'ingestion multipart sécurisée, validation MIME/codec réelle, lecture de durée par décodeur isolé et contrôle de la taille au niveau proxy et serveur.
3. Vérifier la persistance et l'idempotence transactionnelle des jobs avec le repository PostgreSQL et l'outbox ; ne pas se limiter à un identifiant déterministe (une collision d'insertion doit être traitée).
4. Brancher une capability ASR testée, transcriptions sourcées par horodatage, puis corrections et revue scientifique.
5. Vérifier retries bornés, crash/reprise, DLQ, cloisonnement tenant et non-double débit avant staging.

## Vérifier le code
```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-education-health
git pull --ff-only
PYTHONPATH=domains/education:platform/kernel:platform/api \\
/Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m pytest -q \\
  tests/education/test_study_audio_probe.py \\
  tests/education/test_study_audio_workflow.py \\
  tests/education/test_study_audio_security.py \\
  tests/education/test_study_media_intake.py
npm --prefix apps/web run lint
npm --prefix apps/web run build
```
La réalisation de ces tests et la recette navigateur ne sont pas encore confirmées. Ne pas fusionner dans main sans validation.
