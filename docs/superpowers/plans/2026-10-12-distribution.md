# Plan d'implémentation — Sous-projet 4 : Distribution

Spec : `docs/superpowers/specs/2026-10-12-distribution-design.md` (référencée ci-dessous par « spec §x »).
Branche : `main` (travail direct, à la demande de l'utilisateur).

## Conventions

- **TDD** pour `vto.updates`, `core`, l'API et `desktop` : écrire le test → le voir échouer → implémenter → `pytest` + `ruff check` verts → commit.
- Front : Vitest pour le bandeau ; rendu vérifié à la main dans `vto-app --dev` + `npm run dev`, avec `VTO_UPDATE_URL` pointant vers un manifeste local.
- **Un commit par tâche**, message court en anglais à l'impératif minuscule (`add update manifest`).
- Tests Python : fixture `data_dir`, aucun appel réseau (`httpx.MockTransport`), aucun processus réellement lancé (lanceur injectable), aucun `sleep` réel (horloge et intervalle injectables).
- Routes sous `/api` comme les autres. Textes visibles : français, sans jargon.
- Les builds de release utilisent Python 3.12 (comme la CI) ; le poste de dev est en 3.14 : vérifier que PyInstaller le supporte avant le build local, sinon builder dans un venv 3.12.
- Cocher les cases au fur et à mesure.

---

## Partie A — Préparer le paquet

### Tâche 0 — Version unique (spec §2.2)

- [x] Test : `vto.__version__` est une version PEP 440 valide ; `importlib.metadata.version("vto")` lui est égale.
- [x] `pyproject.toml` : `dynamic = ["version"]`, `[tool.hatch.version] path = "src/vto/__init__.py"` ; dépendance `packaging` ; extra `build = ["pyinstaller"]` (version stable actuelle, vérifiée sur PyPI, compatible 3.12).
- [x] `pip install -e backend[dev]`, `pytest`, `ruff check` verts.
- [x] Commit `read package version from vto init`.

### Tâche 1 — Pack de scènes dans le paquet (spec §2.3)

- [x] `git mv default_scenes backend/src/vto/core/default_scenes`.
- [x] Tests (`test_scenes.py`) : `ensure_default_scenes()` sans argument copie le pack lu via `importlib.resources` ; le paramètre `source` reste utilisable par les tests.
- [x] `scenes.py` : remplacer `DEFAULT_SCENES_SOURCE` (et son commentaire « emplacement provisoire ») par une fonction `default_scenes_source()` basée sur `files("vto.core") / "default_scenes"` (convertie en `Path` : `as_file` si besoin) ; adapter `tools/import_legacy.py` et son aide.
- [x] `pyproject.toml` : ajouter `src/vto/core/default_scenes/**` aux `artifacts` du wheel. Vérifier : `pip wheel backend -w %TEMP%\w` puis le wheel contient les décors et `prompt.md`.
- [x] Commit `move default scenes into the package`.

### Tâche 2 — `vinted.json` numéroté (spec §2.5)

- [x] Tests (`tests/vinted/test_remote.py`) : URL par défaut = `…/main/data/vinted-v1.json` dérivée de `VintedData.FORMAT` ; cache `vinted-v1.json` / `vinted-v1.etag` ; l'ancien cache `vinted.json` est ignoré.
- [x] `schema.py` : constante `FORMAT = 1`, utilisée par le `Literal` de `format` (ou test qui vérifie leur égalité).
- [x] `remote.py` : URL et noms du cache dérivés de `FORMAT`.
- [x] `git mv data/vinted.json data/vinted-v1.json` ; `vto-vinted-catalog --data` par défaut `data/vinted-v1.json` (docstring incluse) ; adapter le test qui compare le fichier du dépôt et la copie embarquée.
- [x] `CLAUDE.md` : commande `vto-vinted-catalog` et chemin de copie mis à jour.
- [x] Commit `serve vinted data under a format-numbered path`.

## Partie B — Package `vto.updates`

### Tâche 3 — Chemins et détection de l'exécutable (spec §2.1)

- [x] Tests `paths` : `is_frozen()` faux en test, vrai si `sys.frozen` est monkeypatché ; `updates_cache_dir()` sous `cache_dir()`, créé à la demande.
- [x] Implémenter dans `core/paths.py`.
- [x] Commit `add frozen detection and updates cache path`.

### Tâche 4 — Manifeste (spec §3.1)

- [x] Tests `tests/updates/test_manifest.py` : manifeste valide ; champ manquant ; champ inconnu accepté et ignoré (un manifeste plus récent ne casse pas une ancienne app) ; `url` en `http://` refusée ; `VTO_UPDATE_URL` en `http://127.0.0.1…` accepté (manifeste local pour l'essai du bandeau), toute autre URL `http://` refusée ; `sha256` qui n'est pas 64 hexadécimaux refusé ; version non PEP 440 refusée ; JSON invalide, code 404, délai dépassé → `ManifestUnavailable` ; `VTO_UPDATE_URL` prioritaire sur l'URL par défaut.
- [x] Implémenter `updates/manifest.py` : modèle pydantic `Manifest`, `fetch_manifest(url=None, transport=None)`, délai 5 s, `follow_redirects=True` (GitHub redirige `releases/latest/download`).
- [x] Commit `add update manifest`.

### Tâche 5 — État de mise à jour (spec §3.2)

- [x] Tests `test_check.py` :
  - `compute_status(current, manifest)` : `required` / `available` / `up_to_date`, y compris `0.3.0rc1 < 0.3.0` et `0.2.10 > 0.2.9` ;
  - `UpdateChecker` : première vérification à `start()`, puis à chaque intervalle (intervalle et attente injectables) ; échec → dernier état valide conservé (`unknown` tant qu'aucune vérification n'a abouti) ; `snapshot()` renvoie `{current, latest, status, notes, can_install}` ; `can_install` suit `paths.is_frozen()` ; `is_required()`.
- [x] Implémenter `updates/check.py` (thread démon, verrou, `stop()`).
- [x] Commit `add update checker`.

### Tâche 6 — Téléchargement et lancement (spec §3.3)

- [x] Tests `test_install.py` :
  - téléchargement en flux dans `updates_cache_dir()`, progression (`received`, `total`) observable pendant le flux ;
  - empreinte bonne → fichier `VirtualTryOn-Setup-X.Y.Z.exe` conservé ; mauvaise → fichier supprimé, `UpdateError` « La mise à jour téléchargée est abîmée… » (messages au tutoiement, comme le reste de l'app) ;
  - erreur réseau → `UpdateError` « Le téléchargement de la mise à jour a échoué… » ;
  - lanceur appelé avec `[chemin, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LOG=<logs>/update-X.Y.Z.log"]` ; `OSError` du lanceur → `UpdateError` « Windows a bloqué la mise à jour. » et le rappel d'arrêt n'est **pas** appelé ; succès → rappel d'arrêt appelé ;
  - `clean_old_installers()` supprime les `.exe` de `updates_cache_dir()` et rien d'autre.
- [x] Implémenter `updates/install.py` : `Installer(launcher=..., on_launched=...)` avec états `idle | downloading | launching | error` ; lanceur par défaut `subprocess.Popen(..., creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP, close_fds=True)`.
- [x] Ajouter `UpdateError` (sous-classe de `VtoError`) dans `updates`.
- [x] Commit `add update download and installer launch`.

## Partie C — API, Vinted et lancement

### Tâche 7 — Routes de mise à jour (spec §3.2, §3.3)

- [x] Tests `test_api_update.py` (checker et installer factices) :
  - `GET /api/update` renvoie le snapshot ;
  - `POST /api/update/install` : 409 si la file de génération n'est pas vide (« Une génération est en cours… »), 409 si un envoi Vinted tourne (« Un envoi Vinted est en cours… »), 409 si `can_install` faux, 409 si rien à installer, 202 sinon ; double appel pendant le téléchargement → 409 ;
  - `GET /api/update/progress` : état, octets, message d'erreur.
- [x] Ajouter à `GenerationQueue` et `VintedWorker` une méthode `is_busy()` testée. Une file **en pause** n'est pas occupée : rien ne tourne, et ses articles reprennent au lancement suivant.
- [x] `routes/update.py` ; `create_app(..., updates=...)` optionnel (les tests existants passent sans).
- [x] Commit `add update routes`.

### Tâche 8 — Envoi Vinted bloqué si mise à jour obligatoire (spec §3.2)

- [x] Tests : `VintedWorker.send` lève `VtoError` « Cette version ne fonctionne plus avec Vinted… » quand le prédicat `update_required` renvoie vrai ; route d'envoi → 409 avec ce message ; connexion et ouverture de liens toujours possibles.
- [x] `VintedWorker(update_required=lambda: False)` par défaut.
- [x] Commit `refuse vinted sending when an update is required`.

### Tâche 9 — Lancement : vérification, arrêt demandé, `--self-check` (spec §3.3, §4)

- [x] Tests `test_self_check.py` (contrôles dans `vto/self_check.py`, appelés par `desktop.py`) :
  - `--self-check --output f` en environnement de dev : code 0, `f` liste chaque contrôle OK ; ressource manquante (monkeypatch) → code 1 et le nom de la ressource dans `f` ;
  - les contrôles : import de tous les sous-modules de `vto` (`pkgutil.walk_packages`), front compilé présent (`index.html`), `vinted.json` embarqué valide, pack de scènes non vide, pilote Playwright présent (`playwright._impl._driver.compute_driver_executable()` existe), pywebview et sa plateforme WinForms importables (pythonnet) ;
  - `request_shutdown()` : appelle `webview.windows[0].destroy()` si une fenêtre existe (webview factice).
- [x] `desktop.py` : créer `UpdateChecker` et `Installer` (avec `on_launched=request_shutdown`), les passer à `create_app` et à `VintedWorker` ; `clean_old_installers()` au démarrage ; arrêter le checker à la sortie.
- [x] Le front compilé doit exister pour le test de succès : marquer ce test `skipif` si `api/static/index.html` manque, et le faire tourner en CI après `npm run build`.
- [x] Commit `add self-check and update wiring to desktop`.

## Partie D — Front

### Tâche 10 — Bandeau de mise à jour (spec §3.4)

- [ ] `types.ts` / `api.ts` : `UpdateSnapshot`, `UpdateProgress`, `getUpdate()`, `installUpdate()`, `getUpdateProgress()`.
- [ ] Tests Vitest `UpdateBanner.test.ts` : rien si `up_to_date` ou `unknown` ; `available` masquable (mémorisé pour la session) ; `required` rouge, non masquable ; « Nouveautés » affiche les notes ; clic → appel d'installation, puis barre de progression en interrogeant `progress` ; erreur 409 ou état `error` → message affiché, bouton réactivé ; `can_install` faux → bouton désactivé avec l'explication ; état `launching` → « Installation… l'application va redémarrer. »
- [ ] `UpdateBanner.vue` (PrimeVue `Message`, `ProgressBar`, `Dialog`) monté dans `App.vue` au-dessus du contenu ; interrogation de `/api/update` au chargement puis toutes les 10 min.
- [ ] Vérifier à la main : manifeste local servi par `python -m http.server`, `VTO_UPDATE_URL=http://127.0.0.1:8000/latest.json`. (`http://127.0.0.1` est accepté pour l'URL du manifeste et celle de l'installeur, tâche 4).
- [ ] Commit `add update banner`.

## Partie E — Empaquetage

### Tâche 11 — Spec PyInstaller (spec §2.3)

- [ ] `packaging/vto.spec` : mode dossier, `console=False`, nom `VirtualTryOn`, icône `packaging/icon.ico` (à fournir par l'utilisateur ; icône neutre provisoire sinon), point d'entrée `packaging/launcher.py` (appelle `vto.desktop.main`) ; `datas` : `vto/api/static`, `vto/vinted/data`, `vto/core/default_scenes` via `collect_data_files` ; `collect_all("playwright")` pour le pilote ; `collect_submodules("vto")` ; métadonnées de version Windows (`version_info`) générées depuis `__version__`.
- [ ] Build local : `npm run build` puis `pyinstaller packaging/vto.spec --noconfirm`.
- [ ] `dist/VirtualTryOn/VirtualTryOn.exe --self-check --output selfcheck.txt` → 0.
- [ ] Lancer l'exe à la main : fenêtre, génération d'un article (clé Gemini du `.env` saisie dans l'app), connexion Vinted et création d'un brouillon. Noter dans ce plan les modules ou fichiers qu'il a fallu ajouter.
- [ ] `.gitignore` : `build/`, `dist/`, `packaging/Output/`.
- [ ] Commit `add pyinstaller spec`.

### Tâche 12 — Installeur Inno Setup (spec §2.4)

- [ ] Installer Inno Setup 6 sur le poste (`winget install JRSoftware.InnoSetup`).
- [ ] Télécharger `MicrosoftEdgeWebview2Setup.exe` (bootstrapper Evergreen) dans `packaging/redist/` ; l'ajouter au dépôt (redistribuable, ~2 Mo) ou le télécharger en CI — choisir le téléchargement en CI depuis l'URL officielle `https://go.microsoft.com/fwlink/p/?LinkId=2124703` pour ne rien versionner de binaire ; build local : même téléchargement par un petit script `packaging/fetch_redist.ps1`.
- [ ] `packaging/installer.iss` : `AppId` (GUID généré une fois, ne plus jamais changer), `AppVersion` passée par `/DAppVersion=`, `PrivilegesRequired=lowest`, `DefaultDirName={localappdata}\Programs\VirtualTryOn`, `DisableDirPage=yes`, français (`Languages\French.isl`), `CloseApplications=yes`, `RestartApplications=no`, `OutputBaseFilename=VirtualTryOn-Setup-{#AppVersion}` ; `[Tasks]` raccourci Bureau ; `[Run]` lancement `postinstall skipifsilent` + relance `Check: WizardSilent` (`nowait`) ; `[Code]` détection WebView2 (clés `HKCU`/`HKLM` `…\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}`, valeur `pv`) et exécution du bootstrapper `/silent /install` si absent, message français en cas d'échec ; aucun `[UninstallDelete]` sur les données.
- [ ] Build local : `iscc /DAppVersion=0.2.0 packaging\installer.iss`.
- [ ] Vérifier sur le poste : installation sans UAC, raccourcis, lancement, réinstallation par-dessus l'app ouverte en `/VERYSILENT` (fermeture puis relance), désinstallation qui conserve `%LOCALAPPDATA%\VirtualTryOn`.
- [ ] Commit `add inno setup installer`.

### Tâche 13 — Manifeste de release (spec §3.1, §5)

- [ ] Tests (`tests/test_make_manifest.py`, le script importé par chemin) : manifeste produit valide pour `vto.updates.manifest.Manifest` ; `sha256` correct ; `minimum_version` lu dans `packaging/minimum_version.txt` (espaces ignorés) ; refus si `minimum_version > version` ; `notes` vides acceptées.
- [ ] `packaging/make_manifest.py --installer … --version … --notes-file … --out latest.json` ; `packaging/minimum_version.txt` = `0.2.0`.
- [ ] Commit `add release manifest generator`.

### Tâche 14 — Workflow de release (spec §5)

- [ ] `.github/workflows/release.yml` (déclenché par `push: tags: ["v*"]`, `windows-latest`, `permissions: contents: write`) : étapes de la spec §5 dans l'ordre ; Python 3.12, Node 24 ; notes extraites par `git tag -l --format='%(contents)' $TAG` ; installation de test dans `$RUNNER_TEMP\vto-install` avec `VTO_DATA_DIR` pointé vers un dossier contenant un fichier témoin ; `gh release create $TAG --draft --title … --notes-file … installer latest.json`.
- [ ] Étape de signature présente avec `if: false` et un commentaire sur ce qu'elle devra signer.
- [ ] `ci.yml` : ajouter `npm run build` avant `pytest` dans le job Windows (pour le test `--self-check` de la tâche 9), ou un job dédié — choisir le plus simple qui garde la CI rapide.
- [ ] Essai : pousser un tag `v0.2.0rc1` sur la branche, vérifier la Release brouillon (installeur + `latest.json`), puis la supprimer avec le tag.
- [ ] Commit `add release workflow`.

## Partie F — Documentation et acceptation

### Tâche 15 — Documentation (spec §8)

- [ ] `docs/aide/installation.md` : télécharger, SmartScreen (« Informations complémentaires » → « Exécuter quand même »), antivirus, WebView2, où sont les données, désinstaller ; captures plus tard.
- [ ] `CLAUDE.md` : commandes de build local, procédure de publication (bump de `__version__` → commit → `git tag -a vX.Y.Z` avec les notes → push du tag → essai de l'installeur du brouillon → publication de la Release), chemins `core/default_scenes` et `data/vinted-v1.json`, sous-projet 4 à jour.
- [ ] Commit `document packaging and release`.

### Tâche 16 — Acceptation (spec §7)

- [ ] Pousser `main` avant de tagger : `vinted-v1.json` est lu sur `main`.
- [ ] Créer un compte Windows local « Essai VTO » (Paramètres → Comptes → Autres utilisateurs) : profil vierge, donc `%LOCALAPPDATA%` vide, sans Python ni Node dans le `PATH`. Le poste est en Windows 11 Famille : pas de Bac à sable Windows ni de Hyper-V.
- [ ] Publier `v0.2.0` puis dérouler la spec §7 dans ce compte :
  1. installation, pas d'UAC, avertissement SmartScreen noté ;
  2. clé Gemini, génération, connexion Vinted, brouillon ;
  3. `v0.2.1` : bandeau, mise à jour en un clic, redémarrage en 0.2.1, données et session intactes ;
  4. `minimum_version.txt` à `0.2.2`, `v0.2.2` : app 0.2.1 → bandeau rouge, envoi refusé, génération possible ;
  5. désinstallation : données conservées.
- [ ] Après l'acceptation, supprimer le compte d'essai.
- [ ] Mettre le statut du sous-projet 4 à ✅ dans `CLAUDE.md`.

---

## Points nécessitant l'utilisateur

- Tâche 11 : icône de l'app (`.ico`, 256×256) — sinon icône provisoire.
- Tâche 11 et 16 : connexion Vinted dans l'exe et dans le compte d'essai.
- Tâche 12 : installation d'Inno Setup sur le poste (winget, sans droits admin en mode utilisateur).
- Tâche 16 : publication des Releases sur GitHub (actions visibles publiquement) et création du compte Windows d'essai.
