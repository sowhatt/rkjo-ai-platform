# CAHIER DES CHARGES — RKJO EDUCATION · EXTENSION SANTÉ ET APPRENTISSAGE AUDIO
**Version : 1.1** | **Date : 12 octobre 2026** | **Statut : version de référence fonctionnelle, réalisation progressive**  
**Périmètre :** étudiants médecine, pharmacie et soins infirmiers ; extensible à d'autres formations.  
**Références sources :** `HEALTH_STUDENT_STREAMS_2026-10-11.md` (V1.0 de l'extension santé), `EDU_AUDIO_BOOK_TRANSLATION_STREAMS_V1.md` (addendum audio/livres), et décisions produit des 12 octobre 2026.  
**Gouvernance :** cette consolidation **ne remplace pas le CDC historique à 56 fonctionnalités** (non disponible comme fichier source sur cette branche), et **ne modifie pas l'architecture des streams A/B/C/D/E/F/G/S/T**. Ne pas fusionner dans `main` sans validation explicite.

---

## 0. Historique et versionnage
| Date | Version | Évolutions | Nature |
| --- | --- | --- | --- |
| 2026-10-11 | 1.0 | Extension étudiants santé, sources CM/TD/TP, fiches, cartes mentales, QCM, planning, streams | Référence existante |
| 2026-10-12 | 1.0 + addendum | Audio CM, ebooks personnels 50 MiB, traduction anglais→français, facturation à la demande | Addendum existant |
| **2026-10-12** | **1.1** | Parcours audio de bout en bout, écoute et saut horodaté, validation scientifique, questions sur le cours, fusion Audio+PDF+notes, évaluation et tarification progressive | **Présente version** |

**Légende :** P0 = MVP indispensable ; P1 = différenciation immédiatement post-MVP ; P2 = évolution avancée. `CONÇU` ne signifie ni développé ni validé.

## 1. Vision et objectifs
RKJO Education doit devenir un **système d'apprentissage personnel ancré dans les cours réels de l'étudiant**, non un simple outil de transcription ou de génération de résumés. Le système ingère les ressources légalement utilisables de chaque étudiant, les relie à son établissement/filière/année/UE, en extrait des concepts **avec provenance**, enseigne, fait pratiquer, évalue en autonomie et adapte le plan de révision.

**Objectifs vérifiables :**
- réduire le délai entre la fin du cours magistral et la disponibilité d'un support de révision exploitable ;
- conserver une correspondance navigable **résumé ↔ transcription ↔ horodatage de l'audio** ;
- signaler sans les inventer les passages incertains, non audibles ou scientifiques sensibles ;
- mesurer l'amélioration des acquis via exercices et évaluations indépendantes, pas uniquement le volume de texte produit ;
- maîtriser les coûts de calcul, sans lancer d'opération payante avant acceptation d'un devis.

## 2. Utilisateurs et périmètre
- **Étudiant** : propriétaire logique de ses ressources privées, autorise les traitements, corrige les transcriptions, consomme les livrables, révise et suit sa progression.
- **Enseignant/encadrant** : consultation/revue dans la limite des permissions obtenues, sans accès implicite aux fichiers privés.
- **Administrateur d'établissement** : habilitations, supervision agrégée, pas d'accès automatique au contenu privé.
- **Exploitant RKJO** : traitement technique, observabilité, qualité et facturation sous contrôle des accès.

Filières initiales : médecine, pharmacie, soins infirmiers. La classification par UE et les suggestions sont indicatives ; l'étudiant peut renseigner le libellé exact de son université.

## 3. Sources d'apprentissage acceptées
| Source | Parcours cible | Limite / restriction |
| --- | --- | --- |
| CM/TD/TP PDF | Prévisualisation sourcée, extraction et apprentissage | Pilote PDF actuel : **15 MiB**, texte numérique principalement |
| Enregistrement de CM | Transcription, horodatages, résumé, QCM | Cible : **50 MiB** par fichier, permission d'enregistrer obligatoire |
| Notes personnelles | Alignement sur l'audio et le PDF, corrections | Texte/PDF et images suivant extraction disponible |
| Ebook personnel acheté | Lecture privée, index de chapitres, résumés autorisés | PDF/EPUB **50 MiB**, aucun contournement DRM |
| Ebook anglais | Traduction pédagogique d'extraits/chapitres autorisés | L'achat seul ne garantit pas les droits de traduction intégrale |
| Exercices/corrigés/annales | Entraînement sourcé et exam blanc non officiel | Étiquetage « source fournie » / « généré » |

**Attention aux 50 MiB audio :** cette limite désigne une taille d'import, non une durée garantie de deux heures. La durée dépend du codec et du débit ; le serveur doit lire la durée réelle dans les métadonnées fiables et rejeter les incohérences.

## 4. Fonctionnalités audio détaillées

### A-01 — Déposer un CM audio (P0)
L'étudiant choisit filière, année, UE et type CM, téléverse MP3/M4A/WAV/WebM/OGG pris en charge après validation réelle du format. Il confirme les droits et consentements appropriés ; en cas d'absence d'autorisation, aucun traitement n'est lancé. Le serveur attribue un identifiant source, une empreinte, un propriétaire/tenant, une version, une durée vérifiée et un état de traitement. Upload résumable / stockage objet envisagé pour fichiers volumineux.

### A-02 — Orchestrer un job durable (P0)
Pipeline : `uploaded → validating → queued → transcribing → needs_review? → structuring → ready`, et états `failed`, `cancelled`, `expired`. Réutiliser la résilience RKJO (idempotence, retries bornés, DLQ, reprise après crash, outbox/notifications) ; chaque transition est journalisée et attribuable. Doubles clics/upload identique ne doivent pas doubler les opérations facturables.

### A-03 — Transcrire avec horodatage (P0)
Segments alignés sur des périodes `start_ms/end_ms`, texte, langue, provenance du fichier, taux/confiance **seulement si mesurable et correctement calibré**, avertissement pour silence/coupure/bruit. Option de diarisation seulement si autorisée et suffisamment fiable, sans identification biométrique des personnes. Glossaire métier par UE (anatomie, pharmacologie, unités, acronymes) avec validation humaine.

### A-04 — Relecture et correction (P0)
L'étudiant peut écouter chaque segment, éditer une transcription erronée, retrouver l'original immuable et sauvegarder une nouvelle version. Toute correction invalide ou régénère explicitement les artefacts dérivés concernés ; ne pas écraser silencieusement les preuves sources.

### A-05 — Résumer sans halluciner (P0)
Deux formats minimum : **Express** (concepts fondamentaux) et **Standard** (plan, notions, définitions, points remarquables, nuances et zones incertaines). Chaque affirmation pédagogique substantielle est rattachée à un ou plusieurs segments originaux avec plages temporelles. Distinction visible entre paroles effectivement enregistrées, reformulation IA et information externe ajoutée. Les formules, dosages, chiffres et recommandations médicales exigent un contrôle renforcé et des alertes en cas d'incertitude.

### A-06 — Aller du résumé à l'enregistrement (P0)
Sur un item du résumé, l'étudiant clique « Écouter la source » ; le lecteur démarre au bon moment et présente le transcript correspondant. Rechercher en texte, filtrer par concept ou chapitre, naviguer avant/après le passage. Aucun horodatage « décoratif » inventé.

### A-07 — QCM et flashcards à partir du cours (P1)
Produire questions, réponses, explications et difficultés, avec liens source audibles. Contrôle de couverture du programme et signalement des notions ambiguës ; ne pas proposer une réponse comme correcte sans justification vérifiable. Un score généré ne prouve pas la maîtrise.

### A-08 — Interroger le cours en langage naturel (P1)
Exemple : « Pourquoi la pression artérielle augmente-t-elle selon mon professeur ? » Le RAG recherche les passages audio/transcript reliés, répond avec citations horodatées et reconnaît quand la source ne contient pas l'explication. Option « Réexplique-moi puis pose-moi trois questions », avec séparation entre source et explication complémentaire.

### A-09 — Fusion Audio + PDF + Notes (P1)
Par UE/séance, relier diapositives/pages, segments d'enregistrement et notes libres. Afficher **concordances, compléments oraux et contradictions**, sans fusionner automatiquement des affirmations incompatibles. Toute divergence importante ouvre une revue utilisateur/enseignant. Générer un support unifié citant **chaque provenance** (audio `mm:ss`, PDF page, note version).

### A-10 — Lacunes et tutorat vocal (P2)
Le Learning Engine utilise performances autonomes, prérequis et erreurs récurrentes pour cibler les séances suivantes. Le Professeur IA peut reformuler oralement, dialoguer et proposer de nouveaux exercices. Ne jamais déduire un acquis du seul fait d'avoir écouté l'audio.

### A-11 — Opérations sur ebooks personnels (P1)
Extraire table des matières, pages, chapitres et langue en respectant droits et DRM. Résumé et traduction **seulement à la demande**, chapitre ou extraits autorisés, avec devis préalable, paiement confirmé et traçabilité de la source originale. Conserver le texte original et les corrections terminologiques ; la traduction intégrale d'un livre protégé n'est pas automatiquement permise par l'achat.

## 5. Contrats et métadonnées minimales
| Objet | Champs / contraintes clés |
| --- | --- |
| `StudyMediaSource` | `source_id`, `tenant_id`, `learner_id`, `ue_id`, `kind`, `mime_verified`, `size_bytes`, `duration_ms?`, `checksum`, `version`, `rights_status`, `retention_policy` |
| `AudioProcessingJob` | `job_id`, `source_id`, `order_id?`, `operation`, `status`, `attempts`, `progress`, `error_code`, `started_at`, `finished_at` |
| `TranscriptSegment` | `segment_id`, `source_id`, `start_ms`, `end_ms`, `text`, `language`, `revision`, `quality_flags[]`, `content_hash` |
| `SourcedLearningArtifact` | `artifact_id`, `artifact_type`, `source_versions[]`, `claims[]`, `citations[]`, `model_version`, `review_status`, `created_at` |
| `CrossMediaAlignment` | `alignment_id`, `ue_id`, `audio_segment_ids[]`, `pdf_segment_ids[]`, `note_ids[]`, `match_quality`, `conflict_status` |
| `AudioSummaryQuote` | `quote_id`, `learner_id`, `source_id`, `duration_verified_ms`, `package`, `price_cents`, `currency`, `expires_at`, `cost_estimate`, `status` |
| `AudioProcessingOrder` | `order_id`, `quote_id`, `payment_status`, `job_id?`, `idempotency_key`, `refund_status`, `actual_provider_cost` |
| `LearningEvidence` | `learner_id`, `skill_id`, `attempt_id`, `assistance_used`, `autonomous_score`, `review_state` |

Les identités proviennent **de la session serveur**, jamais d'un `tenant_id` librement envoyé par le navigateur. Toutes les citations sont recalculées/validées contre des segments persistants et versionnés.

## 6. Parcours métier de bout en bout
1. Connexion étudiante sécurisée → choix filière/année/UE.
2. Dépôt d'un fichier audio autorisé → contrôles sécurité/durée/droits → versionnement.
3. Pré-analyse du coût selon **durée mesurée** et formule → devis explicite, montant affiché en euros avec TVA selon contexte.
4. L'étudiant approuve le devis → confirmation de paiement serveur → création du job **une seule fois** ; aucune transcription payante avant autorisation et paiement.
5. Worker E produit segments horodatés → corrections et validation nécessaires → indexation D → génération A via G.
6. B présente le résumé, le lecteur synchronisé et les incertitudes ; C propose des révisions, puis enregistre les preuves autonomes ; T traite les signalements.
7. P1 : joindre PDF et notes → alignement, revue des contradictions et artefacts multisources.
8. Erreur technique : reprise idempotente ou remboursement/avoir selon règles affichées ; suppression du fichier selon politique de rétention et demande utilisateur.

## 7. Tarification audio et modèle économique
**Décision produit : paiement à la demande pour les résumés audio et pour les résumés/traductions de livres.** L'abonnement Education couvre des services distincts selon ses quotas ; aucune vente implicite lors d'un import.

- Le simulateur existant affiche Express **1,49 €**, Standard **2,49 €**, Révision **3,99 €** pour une tranche de 120 minutes. Il s'agit d'un **prototype indicatif non contractuel**, sans paiement ni transcription.
- **Changement demandé en V1.1 : supprimer l'effet de seuil brutal.** Le prix réel devra progresser avec la durée validée plutôt que doubler à 121 minutes. Hypothèses UX à tester pour la formule Révision : 60 min 2,49 € ; 120 min 3,99 € ; 151 min 4,99 € ; 180 min 5,49 €. Les autres formules sont à calibrer sur les coûts.
- Ne pas coder en dur ces hypothèses comme grille définitive. Grille tarifaire versionnée serveur, devis signé/expirant, calcul en unités minimales, informations fiscales et conditions du remboursement. Garantir `price_quote = price_charged` tant que le devis est valide.
- Mesurer l'usage par `tenant/user/source/job` : minutes ASR, tokens entrée/sortie, coût fournisseur, OCR éventuel, stockage, retries, frais de paiement, marge estimée/réelle.
- Résultat : facture/commande et livraison d'artefacts sourcés ; pas de double débit pour un nouveau rendu ou une erreur de clic.

## 8. Répartition inchangée des streams
| Stream | Responsabilité audio et fusion | Priorité |
| --- | --- | --- |
| **A Professeur IA** | Synthèse ancrée, réexplication, flashcards/QCM, signalement non-sourcé | P0 résumés ; P1 tutorat |
| **B UX** | Import, devis, progression, lecteur horodaté, corrections, vues croisées | P0 import/écoute ; P1 fusion |
| **C Learning Engine** | Diagnostic, répétition espacée, preuves autonomes, adaptation par UE | P1 audio ; P0 socle |
| **D Documents/RAG** | Segment provenance, index multimodal, alignement audio/PDF/notes | P0 index ; P1 fusion |
| **E Multimodal** | Transcription ASR, horodatage, langue, qualité et fallback | P0 audio |
| **F Identité** | Identité étudiant/tenant, habilitations et suppression | P0 transversal |
| **G Model Gateway** | Provider ASR/LLM, budgets, coûts, retries et stratégie fallback | P0 transversal |
| **S Safety** | Autorisation enregistrement, données personnelles, droits ebooks, garde-fous santé | P0 transversal |
| **T Supervision** | Revue des corrections/transcriptions, audit, escalade scientifique | Contrats P0, UX P1 |

## 9. Exigences non fonctionnelles
**Sécurité** : authentification réelle avant pilote public, RBAC/tenant isolation, stockage protégé et destruction contrôlée, antivirus, MIME réel, protection contre instructions malveillantes présentes dans les supports, chiffrement au repos/en transit. Ne pas traiter d'audio clinique contenant des données patient identifiables dans le pilote.

**Qualité scientifique** : métriques WER/CER sur corpus autorisé, contrôle nombres/unités/dosages, vérification de la correspondance `claim ↔ timestamp ↔ transcript`, revue humaine des passages dangereux ou incertains. Les réponses aux questions personnelles de santé doivent suivre des contrôles spécifiques.

**Fiabilité** : idempotence entre tentative d'upload, devis, paiement, création job et génération ; retries bornés/DLQ ; récupération crash worker ; traçabilité et audit des versions. Les appels provider doivent être isolés et temporisés.

**Accessibilité et connexion** : conception mobile-first, états et erreurs compréhensibles, lecture segmentée, reprise d'upload sur connexion instable ; prévoir quotas pour établissements sans ordinateurs individuels.

**Performance** : objectifs chiffrés à définir après benchmark représentatif ; toujours afficher un vrai état de traitement, pas de faux pourcentage.

## 10. Critères de recette
| Identifiant | Scénario attendu |
| --- | --- |
| REC-01 | Import audio autorisé reconnu/contrôlé ; format interdit, fichier trop volumineux, tenant tiers rejetés |
| REC-02 | Job en échec/reprise ne produit pas de double facture, ni transcription perdue |
| REC-03 | Tous les passages d'un résumé test renvoient à un segment auditable de l'audio |
| REC-04 | Un clic « écouter la source » positionne le lecteur sur le bon segment temporel |
| REC-05 | Correction d'un transcript met à jour/expire les artefacts dérivés |
| REC-06 | Termes médicaux, chiffres et unités douteux sont signalés ou revus |
| REC-07 | QCM produit à partir de la source et score autonome distinct de l'aide IA |
| REC-08 | Question non couverte par la source : absence de réponse inventée |
| REC-09 | Fusion PDF+audio+notes conserve trois références distinctes et signale les contradictions |
| REC-10 | Devis affiché et accepté avant traitement ; montant stable et remboursement/reprise si incident |
| REC-11 | Progression tarifaire sans doublement brutal après 120 minutes (après implémentation V1.1) |
| REC-12 | Droits d'enregistrement/DRM/licence respectés et suppression effective vérifiable |
| REC-13 | Test de révision avant/après et suivi des gains d'apprentissage sur échantillon consenti |

## 11. Indicateurs produit et pilotes
- **Technique** : WER par type audio, durée traitement / minute source, % de segments sourcés, erreurs par 100 jobs, DLQ, coûts et marge réelle par formule.
- **UX** : import terminé, corrections effectuées, proportion de résumés consultés, taux « écouter la source », demandes de support, abandon à l'étape du devis.
- **Pédagogie** : gain pré-/post-test à difficulté comparable, rétention à J+7/J+30, maîtrise autonome des prérequis, fidélité des QCM aux sources.
- **Commercial** : conversion devis→commande, panier moyen, taux de remboursement, coût moyen d'une transcription/résumé par profil.

Premier pilote : CM autorisé de **30 à 120 minutes**, avec PDF et notes facultatifs ; comparaison manuelle à une transcription de référence ; suivi des erreurs et capacité de correction ; **pas de paiement réel** avant fiabilisation des parcours.

## 12. Feuille de réalisation par priorité (sans sprint imposé)
| Priorité | Lot | Livrable vérifiable |
| --- | --- | --- |
| **P0.1** | Admission et sécurité audio | Endpoint authentifié, contrôle réel fichier, durée, droits, stockage provisoire, propriétaire |
| **P0.2** | Orchestration durable RKJO | Job idempotent, suivi d'état, retries, DLQ, tests crash/reprise |
| **P0.3** | Transcription ASR et validation | Transcript horodaté éditable, flags d'incertitude, versions |
| **P0.4** | Résumé scientifique sourcé | Synthèse reliée aux segments et lecteur « écouter la source » |
| **P0.5** | Mesure de coût et devis | Coût réel par job ; nouveau barème progressif ; aucune vente avant contrôles |
| **P1.1** | Révisions sur audio | Flashcards, QCM, questions RAG, preuves autonomes |
| **P1.2** | Fusion multimodale | Alignement audio/PDF/notes, contradictions, synthèse unifiée |
| **P1.3** | Ebooks achetés | 50 MiB PDF/EPUB autorisés, résumé/traduction à la demande |
| **P2** | Professeur vocal et adaptation avancée | Dialogue oral, ciblage de lacunes, métriques pédagogiques |

## 13. État réel au 12 octobre 2026
**Développé et observé** : interface PDF pilote et connexion locale, simulateur de prix audio, route d'estimation et contrats d'admission audio/ebook ; dernières captures montrent **151 min → 7,98 € en formule Révision** selon l'ancienne règle. Le client a rapporté un build Next.js et lint OK (2 avertissements préexistants).

**Pas encore livré** : import audio réel, ASR, suivi de job durable audio, lecture horodatée, résumé audio IA, QCM audio, fusion Audio/PDF/notes, tarif progressif actif, paiement, traduction d'ebook. Ce CDC **ne prétend pas** valider ces fonctions.

**Version suivante proposée : 1.2** après réalisation et recette du premier parcours audio P0, sans présumer de sa date.
