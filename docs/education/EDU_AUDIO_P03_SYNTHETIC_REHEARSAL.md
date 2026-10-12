# RKJO Education — P0.3 : répétition synthétique de la chaîne durable
12 octobre 2026 | Branche isolée `feat/edu-health-study-pipeline-v1`

## Réalisé
- Générateur déterministe d'un WAV mono PCM 16 bits : son artificiel, sans paroles ni données personnelles.
- Entrée sur la base PostgreSQL dédiée : un étudiant fictif et un seul enregistrement `rkjo-synthetic-lecture.wav`.
- Admission de la source seulement si tenant, étudiant, expiration, état et empreinte SHA256 correspondent à la fixture générée.
- Création de `WorkflowExecution` avec premier step RUNNING et de `workflow_outbox` dans **la même transaction** via le `PostgreSQLWorkflowUnitOfWork` existant.
- Insertion SQL `ON CONFLICT DO NOTHING` et clé de workflow déterministe : les répétitions ne doivent ni modifier l'exécution en cours, ni dupliquer le message.
- La file `rkjo.education.audio.synthetic.rehearsal.disabled` n'est **pas une vraie file de traitement**. Aucun publisher, worker ni ASR n'est déclenché.
- Tests d'isolation, de doublon, d'état de workflow et de ligne d'outbox non publiée. Test PostgreSQL opt-in et test de génération WAV hors base.

## Pré-requis
PostgreSQL de test uniquement : `rkjo_education_audio_test` sur port local 55432. Réutiliser la variable `RKJO_EDUCATION_AUDIO_TEST_DATABASE_URL` déjà configurée **uniquement si le terminal est le même**. Si un nouveau terminal est ouvert, réinitialiser la variable sans imprimer les secrets.

## Tests
```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-education-health
git pull --ff-only
PYTHONPATH=domains/education:platform/kernel:platform/api \
/Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m pytest -q \
  tests/education/test_study_audio_rehearsal.py \
  tests/education/test_study_audio_staging_postgres.py
```
Avec la variable de test PostgreSQL présente, résultat visé : `4 passed` (3 tests rehearsal, 1 stockage). Sans variable, deux tests sont ignorés.

## Important
Ceci vérifie seulement l'admission et la durabilité de l'orchestration, **pas** une transcription ou un résumé. Ne jamais démarrer `OutboxPublisher` sur la base de test avant de purger l'outbox synthétique. Le traitement et les coûts IA restent désactivés. La nomenclature de fichier et SHA-256 est réservée à cette répétition ; ne pas utiliser pour autoriser des enregistrements réels.

### Étape suivante
Tests de crash/reprise et transaction rollback, puis raccordement à une vraie capacité ASR avec qualité et horodatage. Prévoir politique de suppression automatique et stockage objet chiffré avant le pilote réel.
