# RKJO Education — Gate identité avant intégration Next Best Action PWA
13 octobre 2026 · branche `feat/edu-health-study-pipeline-v1`

## Vérifications
- Recette locale du 13/10 : 23 tests C + F + API réussis, lint et build Next.js réussis. Ce résultat ne couvre pas l'authentification bout-en-bout entre Next.js et FastAPI.
- `EducationSession.tsx` lit `learnerId` depuis la query string.
- Les proxies Next.js historiques `/api/education/attempts/[attemptId]/submit` et `/api/education/proof-challenges/[challengeId]/submit` transmettent `X-API-Key: RKJO_OPERATOR_API_KEY`.
- Le nouvel endpoint `GET /education/attempts/{attempt_id}/questions/{question_id}/next-action` exige un sujet Bearer et un tenant **UUID**, le sujet devant correspondre au learner UUID.
- Le pilote `studyPilotSession.ts` utilise `sub=etudiant-pilote` et `tenant=local-education-pilot` : cette session est volontairement incompatible avec le nouvel endpoint.

## Décision
**Ne pas** brancher directement `EducationSession.tsx` sur le nouvel endpoint. Éviter tout fallback implicite sur une clé opérateur et éviter de croire le learnerId transmis dans l'URL.

## Contrat à établir
1. Introduire un mapping serveur authentifié `account_subject → learner_uuid` au sein de `tenant_uuid` ; refuser par défaut si absent. Le learner UUID et le tenant UUID ne doivent pas provenir du navigateur.
2. Pour les étudiants, migrer les endpoints de tentative et preuve vers une authentification Bearer individuelle avec vérification propriétaire. Conserver les opérations administratives sous rôle opérateur distinct.
3. Ajouter au Next.js un proxy lecture `next-action` qui propage uniquement une session individuelle vérifiée et émet un Bearer serveur court ; pas de clé opérateur.
4. La décision `missing_prerequisites` doit être dérivée des prérequis stockés ; ne pas exposer de paramètre de contrôle au client.
5. Tester les cas 401/403/404 : utilisateur absent, mauvais étudiant même tenant, tenant différent, compte sans learner mapping, tentative étrangère, proof étrangère, et sortie API sans données d'examen.
6. Une fois validé : afficher état chargement/erreur/recommandation dans `EducationSession.tsx` après soumission et preuve, sans afficher « maîtrisé » sur une simple réponse guidée.

## Validation
Ne jamais considérer le seul passage de 23 tests et du build comme preuve d'un parcours complet. Une recette navigateur locale à deux identités distinctes est requise.
