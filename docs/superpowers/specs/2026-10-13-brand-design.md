# Sous-projet 6 — Marque & UI (Wearo) — Design

Date : 2026-10-13
Statut : validé en brainstorming ; **piste A retenue** le 2026-10-13 sur la planche (https://claude.ai/artifact/Ey7VNekjAuGPJexc4mTDRV)

## 1. Contexte

L'app s'appelle « Virtual Try-On » : un nom technique, une icône provisoire « VT » (`packaging/make_icon.py`), le thème PrimeVue Aura en teal (presque le vert de Vinted) et des écrans fonctionnels mais bruts. Elle va être vendue sur abonnement à des vendeurs non techniques, face à des concurrents installés (Fripio, Vintapp, VintyLook, Vinkit, Vinteer, Cabine.ai…). Ce sous-projet lui donne une marque et une interface à la hauteur d'un produit payant, sans toucher aux parcours.

### 1.1 Décisions (prises en brainstorming)

| Sujet | Décision |
|---|---|
| Nom | **Wearo** (« wear » + o, se lit « ouéro »). Pas de « Vint- » (marque Vinted) ni de « Frip- » (trop proche de Fripio) |
| Ton | Chaleureux et accessible : couleurs douces, coins arrondis, tutoiement (déjà en place) |
| Couleur | Primaire **abricot/corail** (~`#E8774A`), fond crème (~`#FBF7F2`), texte prune foncé |
| Périmètre | Marque + app + site (pages et e-mails du Worker) |
| Renommage Windows | Complet : exe, installeur, dossier d'installation **et** dossier de données, avec migration automatique |
| UI | Nouvelle DA et écrans repensés ; mêmes parcours, même API, mêmes stores |

Approches écartées : renommer seulement le nom affiché (`VirtualTryOn.exe` resterait visible) ; garder le dossier de données (moins propre, et le chemin apparaît dans l'aide) ; refonte des parcours (assistant, tableau de bord : long, touche aux stores et aux tests) ; landing marketing complète (à faire plus tard, avec un domaine).

### 1.2 Inchangé

Restent internes : le package `vto`, les commandes `vto-*`, les variables `VTO_*`, l'`AppId` Inno Setup, le dépôt GitHub, le nom du Worker `vto-licence` et son URL `*.workers.dev`, la base D1.

### 1.3 Hors périmètre (à faire par l'utilisateur)

- Vérifier « Wearo » à l'INPI et à l'EUIPO, et la disponibilité de `wearo.fr` / `wearo.app`.
- Renommer le produit dans le tableau de bord Stripe (nom affiché au paiement et sur les factures).
- Plus tard : domaine personnalisé pour le Worker et l'expéditeur des e-mails, landing marketing, signature de code au nom de Wearo.

## 2. Identité

### 2.1 Palette

| Rôle | Valeur de départ | Usage |
|---|---|---|
| Primaire | abricot `#E8774A` (échelle 50→950) | boutons principaux, état actif, liens, focus |
| Fond | crème `#FBF7F2` ; surfaces `#FFFFFF` | fond d'app, cartes |
| Neutres | gris chauds (échelle 0→950) | bordures, textes secondaires |
| Texte | prune `#2E1F2B` | texte principal |
| Succès | sauge | publié, validé |
| Avertissement | ambre | bandeaux d'attention |
| Erreur | rouge doux | erreurs, suppression |

Chaque couple texte/fond utilisé doit atteindre le contraste **AA** (4,5:1 ; 3:1 pour les grands textes et les éléments d'interface). Le texte sur un bouton abricot se vérifie en particulier : on fonce la teinte du bouton (600/700) si le blanc ne passe pas.

### 2.2 Typographie et logo

Deux pistes, départagées sur la planche (§3) — **la piste A est retenue** :

- **A** — *Plus Jakarta Sans* partout ; logo en mot-symbole arrondi « wearo » dont le « o » final dessine un cintre.
- **B** — titres en *Fraunces* (serif douce, axe « SOFT »), interface en *Plus Jakarta Sans* ; pictogramme cintre et étincelle à côté du mot.

Les polices sont sous licence OFL, en woff2 **auto-hébergées** dans le front : l'app tourne hors ligne et n'appelle aucun service tiers. Le logo est vectorisé (chemins SVG, sans dépendre de la police), ce qui permet de l'afficher partout : app, pages du Worker, icône.

### 2.3 Ressources

```
brand/
  logo.svg          logo complet (pictogramme + mot)
  logo-mark.svg     pictogramme seul (icône, favicon)
  tokens.json       palette, rayons, ombres : source des valeurs du thème
  README.md         règles d'usage courtes (marges, tailles mini, fonds autorisés)
```

`packaging/make_icon.py` rend `brand/logo-mark.svg` avec Playwright (déjà une dépendance), puis PIL produit `packaging/icon.ico` (16, 24, 32, 48, 64, 128, 256) et `frontend/public/favicon.png`. Les fichiers générés sont commités, comme l'icône actuelle.

## 3. Planche de DA (point d'arrêt)

Avant tout code d'interface, un Artifact privé « Planche Wearo » montre : la palette avec les contrastes, les pistes A et B (logo, titres, texte courant, boutons, champs, tags), l'icône en 16, 32 et 256 px, et deux écrans maquettés (liste des articles, relecture) dans chaque piste. L'utilisateur choisit une piste, et le choix est consigné en tête de ce document.

## 4. Renommage et migration

### 4.1 Dossier de données

`vto.core.paths` :

- `APP_NAME = "Wearo"`, `LEGACY_APP_NAME = "VirtualTryOn"`.
- `migrate_legacy_data_dir() -> str` : sans `VTO_DATA_DIR`, si `…\VirtualTryOn` existe et que `…\Wearo` n'existe pas, `os.rename` de l'un vers l'autre. Les deux sont dans `%LOCALAPPDATA%`, donc sur le même volume, et le renommage est atomique : ni copie ni suppression. La fonction rend une phrase pour le log (« rien à migrer », « données déplacées », « déplacement impossible : … »). Elle ne lève jamais d'exception.
- `data_dir()` : si `…\Wearo` est absent et `…\VirtualTryOn` présent, elle rend l'ancien dossier. Si le renommage échoue (fichier verrouillé, par exemple par un Chrome resté ouvert sur le profil Vinted), l'app tourne donc normalement sur l'ancien dossier et retente au lancement suivant. Les données ne sont jamais dédoublées ni perdues.
- `desktop.main()` appelle la migration **en premier**, avant `setup_logging()` : sinon `logs_dir()` créerait un `…\Wearo` vide qui bloquerait la migration. Le résultat est journalisé juste après. `--self-check` ne migre pas.

Le profil Chrome (`browser-profile`) ne contient pas de chemin absolu bloquant : la session Vinted survit au déplacement, ce que l'essai réel vérifie (§8).

### 4.2 Nom affiché

« Wearo » remplace « Virtual Try-On » dans le titre de la fenêtre pywebview, le `<title>` du front, la barre latérale, l'accueil, l'API (`FastAPI(title=…)`, page `MISSING_FRONT`), l'aide de la CLI, le rapport `--self-check`, la page d'aide et le README du front.

### 4.3 Exécutable et installeur

- `packaging/vto.spec` : nom `Wearo`, d'où `dist/Wearo/Wearo.exe`. Les ressources de version (`OriginalFilename`, `ProductName`, `FileDescription`) sont mises à jour.
- `vto.updates.install` : l'installeur téléchargé s'appelle `Wearo-Setup-{version}.exe` ; `clean_old_installers` retire aussi les `VirtualTryOn-Setup-*`.
- `packaging/installer.iss` :
  - `AppName "Wearo"`, `AppExe "Wearo.exe"`, `AppPublisher "Wearo"`, `OutputBaseFilename=Wearo-Setup-{#AppVersion}` ;
  - `DefaultDirName={autopf}\Wearo` et **`UsePreviousAppDir=no`**, sinon Inno réinstalle dans l'ancien dossier, retrouvé grâce à l'`AppId` ;
  - `AppId` **inchangé** : la nouvelle version remplace l'ancienne dans « Applications installées », et la désinstallation pointe sur le nouveau dossier ;
  - `[InstallDelete]` : `{autopf}\VirtualTryOn` (programme seul, les données sont ailleurs), `{autoprograms}\Virtual Try-On.lnk`, `{autodesktop}\Virtual Try-On.lnk` ;
  - `PrepareToInstall` attend jusqu'à 15 s que `VirtualTryOn.exe` ne tourne plus. Lors d'une mise à jour en un clic, l'ancienne app se ferme d'elle-même juste après avoir lancé l'installeur, et `CloseApplications` ne la couvre plus puisqu'elle n'est pas dans le nouveau `{app}`. Si elle tient encore, l'installation continue : l'ancien dossier reste, sans danger, et disparaît à la mise à jour suivante.
- `.github/workflows/release.yml` : nouveaux chemins et noms, titre de Release « Wearo X.Y.Z », plus un test de **mise à jour depuis la dernière Release publiée** (§8).
- `minimum_version.txt` ne bouge pas. Le Worker sert l'installeur d'une Release d'après son extension `.exe` (`worker/src/files.ts`), quel que soit son nom.

## 5. Interface de l'app

### 5.1 Socle

- `frontend/src/theme.ts` : preset `definePreset(Aura, …)` alimenté par les valeurs de `brand/tokens.json` (recopiées, le front ne lit pas en dehors de `frontend/`). Il fixe la primaire abricot, les surfaces crème et chaudes, des rayons de 12 px (16 px pour les cartes), des ombres douces, un focus visible, des boutons et champs un peu plus hauts, des tags en pilule, et les styles du Toast et du ConfirmDialog. `main.ts` l'utilise à la place du preset teal.
- `frontend/src/style.css` : jetons `--w-*` (espacements, rayons, ombres, échelle typographique), `@font-face` des polices (`frontend/src/assets/fonts/`). Les utilitaires `.stack`, `.row` et `.muted` sont conservés.
- Icônes : la police de `lucide-static` (ISC) remplace les `pi pi-*` de nos composants (une cinquantaine d'occurrences) en gardant l'API par classe (`icon="icon-refresh-cw"`). `frontend/scripts/icons.mjs` génère `src/icons.css` (woff2 seul, icônes utilisées seulement) ; un test vérifie qu'aucune classe utilisée ne manque. `primeicons` est retiré ; PrimeVue garde ses icônes internes.
- Composants partagés, sans logique métier, dans `components/ui/` :
  - `AppLogo.vue` : logo SVG, avec ou sans le mot, et une taille ;
  - `PageHeader.vue` : titre, sous-titre, emplacement d'actions ;
  - `EmptyState.vue` : illustration, titre, texte, action ;
  - `SectionCard.vue` : carte titrée pour les réglages et les formulaires ;
  - `AppBanner.vue` : bandeau arrondi (info, avertissement, erreur), avec une icône, un texte et des actions. Il sert de base commune à `LicenseBanner`, `UpdateBanner`, `QueueBanner` et au message de déconnexion.
- Illustrations : quelques SVG en ligne, simples, dans la palette (cintre, portant, étincelles), sans image externe.

### 5.2 Écrans

Les parcours, les routes, les stores, les appels d'API et les attributs `data-test` restent identiques.

| Écran | Changements |
|---|---|
| Coquille (`App.vue`) | Barre latérale crème avec le logo, une navigation aux icônes Lucide et un actif en pastille abricot, et la version en pied. Bandeaux harmonisés via `AppBanner` |
| Accueil (`WelcomeView`) | Écran centré, logo, indicateur d'étapes « 1 Licence · 2 Clé Gemini », illustration ; consignes Gemini en étapes numérotées |
| Articles (`ArticlesView`, `ArticleList`, `ArticleForm`, `PhotoDrop`) | Liste en cartes avec vignette, titre et statut en pilule (`StatusTag`) ; état vide illustré (« Ajoute ton premier vêtement ») ; grande zone de dépôt accueillante |
| Génération et relecture (`ArticleProgress`, `ArticleReview`, `ListingForm`, `GalleryEditor`, `BackgroundGallery`, `VintedBatchPanel`) | Images plus grandes en grille aérée ; formulaire d'annonce regroupé en sections ; barre d'actions collante en bas (valider, envoyer sur Vinted) |
| Scènes (`ScenesView`) | Grille de cartes, avec une image de couverture par scène |
| Réglages (`SettingsView`, `LicenseSection`, `KeyForm`, `LicenseForm`) | Sections en cartes : Abonnement, Clé Gemini, Vinted, À propos |

On relit les textes au passage (français, tutoiement, sans jargon) sans en changer le fond.

## 6. Site et e-mails (Worker)

- `worker/src/pages.ts` : la CSS de `htmlPage` reprend la palette Wearo, mode sombre compris. L'en-tête porte le logo SVG en ligne. Le titre devient « … · Wearo », et le pied de page et l'accueil sont mis à jour. Les polices restent la pile système : aucune requête vers un service tiers (RGPD), le logo vectorisé portant seul l'identité.
- `worker/src/email.ts` : sujet « Ta clé de licence Wearo », en-tête avec le nom en couleur (texte stylé, pas d'image, souvent bloquée par les messageries), bouton abricot, styles en ligne.
- `wrangler.toml` : `EMAIL_FROM = "Wearo <onboarding@resend.dev>"`, et le commentaire de `STRIPE_PRICE_IDS` est renommé. Le déploiement est fait par l'utilisateur ou avec son accord.
- `docs/aide/installation.md` est regénéré dans `worker/src/aide.generated.ts` par `worker/scripts/build-aide.mjs`.

## 7. Documentation

- `docs/aide/installation.md` : nom, chemins (`%LOCALAPPDATA%\Wearo`, `%LOCALAPPDATA%\Programs\Wearo`), et une phrase : « Virtual Try-On s'appelle maintenant Wearo : tes données ont été déplacées automatiquement. »
- `CLAUDE.md` : titre, chemins, roadmap (ligne 6).

## 8. Tests et vérification

- **Python** (`backend/tests/test_paths.py`) : rien à migrer ; migration réussie (articles, `license.json`, `browser-profile` présents à l'arrivée, ancien dossier absent) ; échec de `os.rename` simulé, avec repli de `data_dir()` sur l'ancien dossier ; `VTO_DATA_DIR` désactive la migration ; dossier neuf sans ancien. Tests de mise à jour et de manifeste adaptés au nouveau nom d'installeur, plus le nettoyage des anciens installeurs.
- **Front** : les tests Vitest existants restent verts sans changer leurs assertions métier ; tests légers pour `EmptyState`, `PageHeader` et `AppBanner`.
- **Worker** : tests des pages et des e-mails adaptés aux textes ; `npm run typecheck`.
- **CI** (`release.yml`) : en plus du parcours actuel, installer en silencieux la dernière Release publiée (VirtualTryOn), créer `%LOCALAPPDATA%\VirtualTryOn\articles\témoin`, installer la nouvelle, lancer `Wearo.exe --self-check` puis la vraie app quelques secondes (pour déclencher la migration), et vérifier : `%LOCALAPPDATA%\Wearo\articles\témoin` présent, ancien dossier de données et ancien dossier d'installation absents.
- **Essai réel sur le poste** : depuis la v0.2.2 installée et pleine de données, mise à jour en un clic vers une préversion Wearo. Vérifier un seul raccourci « Wearo », les articles, les scènes et la licence retrouvés, un brouillon Vinted envoyé **sans reconnexion**, puis une désinstallation qui conserve les données.
- **Visuel** : tour de tous les écrans en `vto-app --dev` + `npm run dev` (accueil, articles vide et rempli, génération, relecture, scènes, réglages, chaque bandeau), comparé à la planche.

## 9. Choix sur la planche (2026-10-13)

Piste **A** retenue : *Plus Jakarta Sans* seule (400 à 800), logo « wear » + « o » cintre (cercle épais abricot surmonté d'un crochet), icône abricot avec le « o » cintre prune. Repris des maquettes :

- boutons principaux en abricot 500 avec texte prune (5,3:1), le blanc sur abricot étant écarté ;
- liste des articles en grille de cartes avec filtres (Tous, À relire, Prêts à envoyer, Publiés) ; la fiche d'un article s'ouvre en pleine largeur avec un lien « Mes articles » ;
- relecture en deux colonnes (photos, annonce) avec une barre d'actions collante en bas ;
- barre latérale sable 100, élément actif sur fond blanc avec une icône abricot.
