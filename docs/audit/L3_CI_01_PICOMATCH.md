# PR #18 — résolution du blocage picomatch, 18 novembre 2026

## Provenance du candidat

HEAD distant vérifié avant intervention : d2521db0bd4dbfef7fb9fa11a42b0c0e49fe9b19.
f7386c785825434254fcf4906c57cd0d526c14d6 est son enfant direct, auparavant local :
il ne change que L3_CI_01_QUALIFICATION.json, L3_CI_01_RESULTAT.md,
L3_QUALIFICATION.json et RKJO_SOCLE_L3_RESULTAT.md (405 ajouts, 12 suppressions).
Aucun changement de code, de test, de workflow CI ou de dépendance entre ces SHA.
La CI 44142422117 testait d2521db via le merge synthétique
674561df0696465ae52654643eed0ef61ba48a3d. Les vingt démarrages AMQP sont réutilisés,
pas réexécutés. La branche PR avance en fast-forward pour inclure le bilan f7386c7
et le présent constat ; la nouvelle CI qualifiera ce HEAD final explicitement.

## Avis actuel et décision minimale

[GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf) a été
**retiré le 18 novembre 2026**. La page garde sa plage historique <=4.0.7 et
« aucune version corrigée ». Le registre npm confirme latest=4.0.7 ; aucune
version corrigée n'est inventée. Le [mainteneur](https://github.com/micromatch/picomatch/pull/235)
conteste la qualification de vulnérabilité et rappelle que les motifs glob/regex
doivent provenir d'une source de confiance. Le retrait ne rend pas toute regex
arbitraire sûre et ne constitue pas une acceptation locale de risque.

Après retrait, `npm ci` puis `npm audit --audit-level=moderate`, sans exclusions,
donnent zéro vulnérabilité avec le lock existant. **Correction de dépendances
nécessaire : aucune.** La plus petite résolution compatible est de conserver
package.json et package-lock.json octet pour octet et de requalifier après ce
changement externe vérifié. Aucun override picomatch, seuil abaissé, audit
supprimé, exception de risque ou changement de paquet pour masquer l'alerte.

## Toutes les chaînes du lock (graphe factorisé)

Racine unique : `web → eslint-config-next@16.4.6` (devDependency).
La table donne les arêtes pertinentes ; leurs compositions couvrent les chemins
directs, partagés et les peers du lock, y compris ceux dédupliqués par `npm ls`.

| Parent | Dépendants pertinents |
| --- | --- |
| eslint-config-next 16.4.6 | @next/eslint-plugin-next 16.4.6 ; eslint-import-resolver-typescript 3.10.1 ; typescript-eslint 8.72.2 |
| @next/eslint-plugin-next 16.4.6 | fast-glob 3.3.1 |
| fast-glob 3.3.1 | micromatch 4.0.8 |
| micromatch 4.0.8 | picomatch 2.3.2 |
| eslint-import-resolver-typescript 3.10.1 | tinyglobby 0.2.17 |
| typescript-eslint 8.72.2 | @typescript-eslint/eslint-plugin, parser, typescript-estree, utils (tous 8.72.2) |
| @typescript-eslint/eslint-plugin 8.72.2 | type-utils, utils ; peer parser (8.72.2) |
| @typescript-eslint/parser 8.72.2 | typescript-estree 8.72.2 |
| @typescript-eslint/type-utils 8.72.2 | typescript-estree, utils (8.72.2) |
| @typescript-eslint/utils 8.72.2 | typescript-estree 8.72.2 |
| @typescript-eslint/typescript-estree 8.72.2 | tinyglobby 0.2.17 |
| tinyglobby 0.2.17 | picomatch 4.0.5 ; fdir 6.5.0 |
| fdir 6.5.0 | peer picomatch 4.0.5 (dédupliqué) |

Les deux entrées du lock sont `node_modules/picomatch` (2.3.2) et
`node_modules/tinyglobby/node_modules/picomatch` (4.0.5), toutes deux `dev: true`.
`npm ls picomatch --all --omit=dev` est vide. Aucun import picomatch/micromatch/
fast-glob/tinyglobby dans les routes ou le code applicatif du dépôt.
Ces copies servent au lint, à la résolution TypeScript et à l'outillage de
développement/qualification ; les motifs proviennent de la configuration du
dépôt, pas d'un paramètre HTTP. Elles ne sont pas une dépendance du graphe npm
de production. Cette conclusion est bornée aux entrées du lock examinées ;
elle ne prétend pas auditer tout code tiers éventuellement embarqué par Next.

## Solutions examinées

* Mise à jour compatible du parent : latest eslint-config-next et plugin Next
  restent 16.4.6, déjà utilisés. Le resolver latest 4.4.5 sort de la contrainte
  ^3.5.2 du parent et dépend toujours de tinyglobby : il ne supprime pas la chaîne.
* Suppression d'un parent inutilisé : aucun. eslint.config.mjs importe réellement
  core-web-vitals et typescript ; supprimer leur parent retirerait des contrôles.
* Remplacement maintenu documenté par Next : utiliser directement son plugin est
  supporté, mais ce plugin garde fast-glob → micromatch → picomatch. Il ne résout
  pas l'ancienne alerte et nécessiterait de reconstruire les autres règles.
* Remplacer le moteur de lint ou maintenir un fork de glob serait une refonte
  disproportionnée, sans nécessité après retrait et réussite de l'audit courant.

## Vérifications reproductibles

Conteneur dédié `node:24-bookworm`, Node 24.22.3, même lock :

```sh
npm ci --no-fund
npm audit --audit-level=moderate
npm run lint -- --max-warnings=0
npm run build
node tests/proxy-security.mjs
```

Tous réussis le 18 novembre : zéro vulnérabilité ; six routes Next réelles
testées avec upstream synthétique. Pas de test AMQP supplémentaire dans cette
vérification. Les logs, versions npm et chaînes sont conservés privément dans
`.test-results/*20261118*`. Le diff vérifie l'absence de modification des deux
fichiers package. La première CI rouge reste conservée ; la nouvelle CI est
justifiée par le retrait vérifié de l'avis, pas par une recherche aléatoire de vert.

La clôture L3-CI-01 reste conditionnée à tous les contrôles de PR puis à la CI
post-fusion. L4 ne commence pas avant cette clôture effective.
