# RKJO Education — Streams étudiants santé
Date : 11 octobre 2026. Addendum au CDC Education existant ; ne remplace ni les 56 fonctionnalités ni l'architecture A/B/C/D/E/F/G/S/T validée.

## Objectif
Les étudiants en médecine, pharmacie et soins infirmiers importent leurs CM, TD, TP, exercices, corrigés et annales. RKJO les relie à leur année, UE et curriculum, puis génère des fiches de révision, cartes mentales interactives, flashcards, QCM, examens blancs et un planning de révisions adaptatif. Les supports générés portent des références à leurs documents sources.

## Streams mis à jour
| Stream | Responsabilité | Priorité |
|---|---|---|
| D Documents/RAG/Curriculum | Import, classification CM/TD/TP, OCR et extraction, index sourcé, versionnage, rattachement UE/notions/compétences/prérequis | P0 |
| C Learning Engine | Diagnostic, calendrier de révisions, répétition espacée, tentatives, preuves autonomes et replanification explicable | P0 |
| G Model Gateway | Profils pédagogiques médecine, pharmacie, infirmier ; routage modèles, validation des formats, coûts et fallback | P0 |
| A Professeur IA | Tutorat ancré dans les cours ; synthèses, cartes mentales, flashcards, QCM et examens avec références vérifiables | P0 |
| B UX étudiant | Accueil visuel, bibliothèque CM/TD/TP, dépôt, fiches, cartes mentales interactives, flashcards, examens et planning | P0 |
| F Identité | Filière, université, année, UE, séparation des ressources et droits sur tous les artefacts | P0 transversal |
| S Safety | Isolation des données, contrôles des supports non fiables, validation des contenus de santé, simulations fictives seulement | P0 transversal |
| E Multimodal | Analyse des images et schémas, notes photographiées, audio de cours, rendu de cartes mentales | P1 |
| T Supervision | Signalement d'erreurs, revue enseignante, alertes, audit des corrections et validations | P1, contrats P0 |

## Contrats transversaux
- **StudySourcePackage** : tenant, étudiant, programme, UE, document, version, type (CM/TD/TP/notes/exercices/corrigé/annales), segments sourcés (page, provenance), statut d'extraction et avertissements.
- **StudyArtifact** : type (fiche/carte mentale/flashcards/QCM/examen), version source, compétence, modèle utilisé, sources de chaque élément, statut de validation. Carte mentale = graphe de concepts et liens ; interface = rendu graphique.
- **StudyPlan** : étudiant, UE, échéance d'examen, disponibilités, séances planifiées, raisons des choix et version.
- **LearningEvidence** : compétence, tentative, aides utilisées, évaluation autonome, résultat contrôlé. Aucun texte généré ne vaut preuve de maîtrise à lui seul.

## Parcours P0
1. L'étudiant choisit sa filière, année, UE et charge un CM et un TD.
2. RKJO extrait, classe, affiche les erreurs éventuelles et conserve les pages d'origine.
3. Il propose une fiche sourcée, une carte mentale, des flashcards et un QCM.
4. Il planifie les séances jusqu'à l'examen selon disponibilités et diagnostic.
5. L'étudiant révise, passe une évaluation autonome et le Learning Engine adapte la suite.
6. Les examens blancs s'appuient sur les cours ; aucune annale générée n'est présentée comme officielle.

## Dépendances et validation
- D fournit des documents versionnés et une provenance à A/C/B.
- G fournit une interface de génération structurée à A, non une décision de maîtrise.
- C décide des prochaines activités à partir de preuves, non de scores inventés.
- F et S s'appliquent à tous les accès et traitements ; T reçoit les alertes requises.
- Tester en premier sur une UE de médecine, avec profils pharmacie et IFSI compatibles.
- Critères : accès croisé rejeté ; sources consultables ; imports idempotents ; artefacts périmés après mise à jour source ; décisions explicables ; tests unitaires, intégration et navigateur.

## État actuel
La branche parente inclut cinq cartes d'accueil et une page de présentation des outils, **pas** les générateurs complets, ni une évaluation de bout en bout validée. Les profils santé et graphes de prérequis existants sont des démonstrations non officielles. Le présent changement est documentaire et n'implique ni build ni déploiement.
