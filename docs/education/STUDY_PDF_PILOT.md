# RKJO Education — Connexion pilote local et analyse PDF

## Périmètre

La page `/education/study-tools` propose désormais une connexion de démonstration par code, puis l'import PDF CM/TD/TP et l'affichage d'extraits sourcés. Aucun JWT n'est saisi dans le navigateur. Next.js crée une session signée dans un cookie HttpOnly SameSite=Strict, de durée 30 minutes ; il émet un JWT interne de 60 secondes pour l'API FastAPI au moment de la requête.

**Ce n'est pas une authentification de production.** Le pilote n'est activé que si `NODE_ENV=development`, `RKJO_EDUCATION_STUDY_PILOT=enabled` et les secrets sont configurés. Le proxy impose l'origine locale et une URL API loopback HTTP.

## Démarrage sécurisé local

Dans un premier terminal, depuis le worktree :

```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-education-health
umask 077
# Fichier local non commité, à détruire après le pilote.
if [ ! -f /tmp/rkjo-education-local-pilot.env ]; then
  {
    printf 'export RKJO_JWT_SECRET=%s\n' "$(openssl rand -hex 32)"
    printf 'export RKJO_EDUCATION_PILOT_SESSION_SECRET=%s\n' "$(openssl rand -hex 32)"
    printf 'export RKJO_EDUCATION_PILOT_PASSWORD=%s\n' "$(openssl rand -hex 16)"
    printf 'export RKJO_API_KEY=%s\n' "$(openssl rand -hex 32)"
  } > /tmp/rkjo-education-local-pilot.env
fi
source /tmp/rkjo-education-local-pilot.env
PYTHONPATH=domains/education:platform/kernel:platform/api \
/Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python \
-m uvicorn rkjo_api.main:app --host 127.0.0.1 --port 8020
```

Dans un second terminal :

```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-education-health/apps/web
source /tmp/rkjo-education-local-pilot.env
RKJO_EDUCATION_STUDY_PILOT=enabled RKJO_EDUCATION_API_URL=http://127.0.0.1:8020 npm run dev
```

Ouvrir `http://localhost:3000/education/study-tools` (ou le port affiché par Next.js). Lire localement **uniquement la valeur** de `RKJO_EDUCATION_PILOT_PASSWORD` à partir du fichier privé de pilote ; ne pas copier le fichier ou sa valeur dans Git ou une conversation. Utiliser ce code dans « Se connecter », puis choisir un PDF de test autorisé et sélectionner une UE.

Ne pas recréer le fichier de secrets entre les deux démarrages. Ne pas démarrer deux Uvicorn sur le même port.

## Vérifications

```bash
npm --prefix apps/web run lint
npm --prefix apps/web run build
PYTHONPATH=domains/education:platform/kernel:platform/api \
/Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m pytest -q \
tests/education/test_study_documents_api.py tests/education/test_study_preview_rbac.py
```

Tester : sans connexion le bouton PDF reste inactif ; code invalide donne HTTP 401 ; code valide ouvre une session ; l'import PDF retourne ses extraits et pages ; « Se déconnecter » invalide le cookie navigateur ; la session expire après 30 minutes ; un fichier non PDF ou image-only est rejeté.

## Limites et sécurité

- Conserver l'application uniquement sur localhost. Aucun serveur public ni données de patients.
- Le code de pilote est partagé entre les testeurs : pas d'identité réelle, pas de gestion des comptes, pas d'autorisation universitaire. Le sujet/tenant du JWT sont fixes et dédiés à la démonstration.
- L'API n'enregistre pas le PDF ; le navigateur et Next.js le transfèrent en mémoire. Ne pas utiliser d'œuvres ou de dossiers sans autorisation.
- Le cookie est HttpOnly et SameSite=Strict, mais non Secure sur HTTP local ; une future session de production nécessitera HTTPS, cookie Secure, fournisseur d'identité, CSRF complet, rate limiting et audit.
- Après le pilote, arrêter les deux serveurs et supprimer `/tmp/rkjo-education-local-pilot.env`. La suppression ne révoque pas une session encore active tant que les serveurs utilisent les clés : **arrêter les serveurs également**.
