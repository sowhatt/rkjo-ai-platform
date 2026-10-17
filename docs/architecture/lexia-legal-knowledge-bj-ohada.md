# RKJO × LexIA — Legal Knowledge Bénin/OHADA

## Objectif et contrat

La recherche RAG retourne uniquement des sources candidates. Une présence dans pgvector, une URL HTTPS ou un checksum renseigné ne constituent pas une vérification juridique.

Champs requis pour le contrôle pilote : tenant_id, canonical_id, title, article, source, official_source_url, checksum_sha256, effective_from, verification_status, domain=droit, country=BJ ou OHADA.

Champs temporels : effective_to (facultatif), status=IN_FORCE ou PARTIALLY_IN_FORCE, date d'effet cible explicitement passée au contrôleur. Un document abrogé peut exiger une recherche historique spécifique et une validation du juriste.

Le contrôle assess_legal_source dans platform/kernel/rkjo_kernel/rag/legal_source_gate.py valide uniquement la structure, le périmètre et l'éligibilité à la revue. trusted_for_citation vaut toujours False : même une métadonnée verified_content est non probante sans comparaison indépendante avec le texte officiel.

## Workflow métier cible — pas encore raccordé

1. Collecter une source institutionnelle vérifiable, enregistrer son émetteur, son URL, sa date de collecte et le SHA-256 calculé sur les octets.
2. Identifier la version, les modifications, les éventuelles abrogations, la date d'application et le champ territorial.
3. Contrôler juridiquement la source avec un professionnel habilité, journaliser la décision et le justificatif.
4. Indexer les fragments avec tenant imposé par authentification, sans mélanger actes privés et corpus juridique.
5. Restituer une citation candidate avec titre, article et provenance ; refuser son utilisation automatique dans un acte.
6. En cas de modification du droit, créer une nouvelle version, conserver l'historique et réévaluer l'applicabilité.

## Points d'attention

- BJ et OHADA ne sont pas interchangeables : le filtre country est technique, pas une décision sur le champ d'application.
- Une URL HTTPS n'est pas une preuve d'officialité ni d'exactitude des données.
- L'indexation effective, le référentiel institutionnel et les validations humaines ne sont pas développés dans ce lot.
- Les règles du modèle LexIA legal/authority.py doivent être harmonisées avec ce contrat avant branchement.

## Recette

PYTHONPATH=domains/education:platform/api:platform/kernel /Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m pytest -q tests/kernel/rag/test_lexia_legal_source_gate.py

Cette suite ne nécessite pas de base. Le test hybride sur pgvector demeure une recette distincte.