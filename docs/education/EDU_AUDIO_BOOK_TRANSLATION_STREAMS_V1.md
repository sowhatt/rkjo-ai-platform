# RKJO Education — CM audio + livres 50 Mo + traduction vers le français
Date : 2026-10-12. Addendum aux streams existants A/B/C/D/E/F/G/S/T. Ne remplace pas l'architecture d'origine.

## Précision produit — livres numériques achetés par l'étudiant

Le cas d'usage cible est un **ebook personnel acquis légalement par l'étudiant** (PDF/EPUB, jusqu'à 50 MiB). L'achat est déclaré par l'utilisateur, mais **n'implique pas automatiquement** le droit de contourner un DRM, de partager l'ouvrage ou d'en créer une traduction intégrale. Le traitement dépend de la licence et du droit applicable.

**Règles de gestion :**
- provenance déclarée : `student_purchased_ebook` ; preuve d'achat facultative et non stockée par défaut (minimisation) ;
- ingestion uniquement si l'étudiant possède le fichier et dispose des droits de le traiter ; aucun contournement DRM ni récupération automatique depuis une boutique ;
- bibliothèque **strictement personnelle**, sans partage ou téléchargement public ; suppression sur demande ;
- traduction anglais → français uniquement des chapitres/extraits autorisés, en préservant la source et la terminologie médicale ; une traduction intégrale exige les droits adéquats ;
- distinguer droit d'étude personnel, licence de traduction, redistribution et accès par modèle tiers ; ne pas présumer que l'achat autorise chacun de ces usages ;
- si ouvrage bloqué par DRM : expliquer la limitation et proposer des passages que l'étudiant peut utiliser légitimement, plutôt que contourner la protection.

## Parcours cibles

1. **Audio CM** : l'étudiant choisit la formation et l'UE, importe une capture audio autorisée (MP3/M4A/WAV/WebM/OGG), confirme l'autorisation d'enregistrement, puis suit le job de transcription ; RKJO préserve horodatage, extrait, version source, incertitudes et éventuellement la séparation des intervenants. L'étudiant corrige les erreurs de transcription avant la génération des fiches/QCM.
2. **Livre numérique** : import PDF/EPUB autorisé (maximum **50 MiB = 52 428 800 octets**), extraction et OCR si nécessaire, table des matières, chapitres/pages, contrôle des erreurs d'encodage et reconnaissance de la langue. Les contenus sont traités par chapitres, jamais par un unique prompt massif.
3. **Anglais → français** : après confirmation des droits de traduction et sélection des chapitres, la génération traduit par petits segments avec mémoire terminologique. Pour chaque segment traduit, conservation de l'original, de la référence chapitre/page, du modèle et des éventuelles incertitudes. Révision humaine privilégiée pour les termes médicaux et posologies. La traduction complète d'un ouvrage protégé exige un cadre d'autorisation adapté et ne doit pas être proposée sans cela.

## Responsabilités des streams

| Stream | Extension |
| --- | --- |
| D Documents / RAG | Admission, gestion des fichiers volumineux, tables des matières, extraction PDF/EPUB, alignement page/chapitre, index source et traduction |
| E Multimodal | ASR/transcription audio + horodatage, détection langue, OCR et figures, correction de transcript |
| G Gateway | Routage ASR/traduction/résumé, limites tokens/coûts, timeouts, providers locaux ou distants, fallback et comparaison qualité |
| A Professeur IA | Fiches, cartes mentales, QCM, flashcards à partir de transcript ou chapitre autorisé, citations et niveau pédagogique |
| B UX étudiant | Sélecteur PDF/audio/livre, progression des jobs, choix chapitre et langue, correction de transcription, affichage original/traduction |
| C Learning Engine | Parcours de révisions basé sur concepts issus des sources, planning par chapitre/UE, preuves autonomes |
| F Identité | Propriété des fichiers, contrôle au niveau tenant/étudiant, suppression et droits par document |
| S Sécurité | Autorisation d'enregistrement, droit de traduire, PI/copyright, confidentialité des voix, injection documentaire, revue humaine santé |
| T Supervision | Validation et corrections de transcription/traduction, signalement scientifique, audit et recours |

## Flux technique cible

- Client → API authentifiée → stockage temporaire chiffré → job durable (stream E / D) → extraction et contrôle qualité → morceaux horodatés ou paginés → index tenant-safe → traduction optionnelle → supports générés → Learning Engine.
- Les fichiers de 50 MiB ne passent pas dans le flux de prévisualisation PDF actuel limité à 15 MiB. Prévoir upload multipart/résumable, validation MIME réelle, quotas, analyse antimalware, hash idempotent et mécanismes de suppression.
- Travail asynchrone avec `job_id`, états `uploaded/queued/processing/needs_review/ready/failed`, progress et retries bornés + DLQ via kernel existant.
- Pour les traductions, envoyer au moteur seulement les morceaux nécessaires, tracer l'alignement original/traduction et permettre l'export **uniquement si les droits le permettent**.
- Qualité : WER pour la transcription sur échantillons autorisés, couverture des pages, alignement source/traduction, terminologie médicale évaluée par experts, citations et coût/temps par Mo ou heure audio.

## Lot actuel et limites

- **Implémenté en code** : contrat `study_media_intake.py` (type, MIME déclaré, limite 50 MiB, droits et consentement), tests unitaires ; deux cartes d'information UX dans `study-tools`.
- **Non implémenté à cette date** : endpoint de téléversement 50 MiB, reconnaissance MIME réelle, traitement asynchrone, ASR, OCR d'ouvrage, EPUB parser, détection automatique de la langue, traduction IA, correction interactive, stockage/persistance, fonctionnalités d'export.
- Ne pas afficher « traité », « transcrit », ou « traduit » dans le produit tant qu'un job réel n'est pas terminé.
- Les vérifications métier et techniques du premier lot nécessitent une exécution pytest, lint et build dans le worktree Mac.
