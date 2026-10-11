# RKJO Education — contrats F/C et S/T selon le schéma utilisateur

**Le schéma fonctionnel de référence reste inchangé.** Cette livraison ne crée ni endpoint, ni connexion à une base, ni supervision WebSocket/SSE.

## API de séance -> Learning Engine (C)
- Pure domain `learning/session_control.py`: PAUSE, RESUME, END.
- Version monotone lors de chaque commande modifiant l'état et de chaque action élève.
- Refus de toute activité après PAUSE / END, et de résultats produits sur une ancienne version.
- La mise en production nécessite : JWT professeur et grants (F), écriture transactionnelle CAS/optimistic concurrency, journal d'audit, idempotency keys, événements durables et contrôles anti-rejeu.

## Garde-fous mineurs (S) -> Supervision (T)
- Contrat `supervision/safety_alerts.py`: `SafetyAlert` typée sans contenu brut, `TeacherAlertSink` injectable et dispatch direct.
- Les alertes ne doivent pas dépendre de la table des preuves.
- L'émetteur, le bus d'événements durable, les permissions professeur, la supervision temps réel et les politiques de filtrage restent à développer.
- La protection des données des mineurs et les règles d'escalade nécessitent validation métier/juridique.

## Tests unitaires locaux
```bash
PYTHONPATH=domains/education:platform/kernel:platform/api \
python -m pytest -q --tb=short \
  tests/education/test_ce1_session_control.py \
  tests/education/test_safety_alert_contract.py \
  tests/education/test_ce1_acg_integration.py
```

La réussite de ces tests ne signifie **pas** qu'une API sécurisée, des alertes réseau ou une persistance sont livrées.
