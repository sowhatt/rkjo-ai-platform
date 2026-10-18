# LexIA — vérification juridique « quatre yeux » (lot 2)

Module : platform/kernel/rkjo_kernel/rag/legal_four_eyes.py.

Deux acteurs distincts, disposant chacun d'une habilitation explicite pour le même tenant et le même dossier, doivent enregistrer deux revues séparées. Le déposant du document ne peut être l'un des validateurs. Les opérations sont transactionnelles avec verrouillage FOR UPDATE du dossier pour éviter une double validation concurrente.

Chaque décision conserve identifiant de personne, note et horodatage dans une table PostgreSQL distincte. Les pièces en quarantaine ou rejetées ne peuvent pas être validées. Un document d'un cabinet étranger est indiscernable d'un document absent. Ni le fait de passer deux revues ni le statut obtenu n'autorise une publication RAG : publishable reste False.

Les habilitations sont provisionnées exclusivement par un administrateur de confiance via grant_reviewer au niveau du service. Ne PAS exposer cet appel en HTTP aux réviseurs. Le contrôle réel de l'identité professionnelle et du rattachement du juriste au dossier doit être intégré à LexIA avant toute mise en production.

Les tables doivent être créées par migration administrative après celles de PostgresLegalReviewInbox ; aucun endpoint de validation ou de publication n'est ajouté dans ce lot. Sur base jetable uniquement, appeler drop_schema() pour le nettoyage.

Limites à lever : identité administrateur fiable lors du provisionnement des habilitations ; révocation, séparation des fonctions, contrôles SQL des droits de modification/suppression, conservation des preuves originales et authentification des sources officielles. Le journal doit être rendu append-only via les privilèges de la base. L'API JWT actuelle ne permet pas encore aux réviseurs de déclencher la décision à quatre yeux.

Recette ciblée : PYTHONPATH=domains/education:platform/api:platform/kernel /Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m pytest -v -rs tests/api/test_lexia_four_eyes_pg_e2e.py

Prérequis : RKJO_LEXIA_TEST_DATABASE_URL vers la base PostgreSQL de test isolée.