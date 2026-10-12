# Sous-projet 4 — Distribution — Design

Date : 2026-10-12
Statut : validé en brainstorming, en attente de relecture

## 1. Contexte

Les sous-projets 1 à 3 ont livré l'app complète (`vto-app`) sur `main`, mais elle ne tourne que depuis un environnement Python de développement. Ce sous-projet la transforme en un installeur Windows qu'un vendeur non technique télécharge, installe sans droits administrateur et met à jour en un clic.

### 1.1 Décisions (prises en brainstorming)

| Sujet | Décision |
|---|---|
| Hébergement | GitHub Releases du dépôt public. L'app lit le manifeste à une URL configurable, que le sous-projet 5 fera pointer vers le Worker |
| Mise à jour | Bandeau « Nouvelle version disponible — Mettre à jour » ; un clic télécharge, vérifie le SHA-256, lance l'installeur en silencieux, ferme l'app ; l'installeur la relance |
| Installation | Par utilisateur, sans UAC, dans `%LOCALAPPDATA%\Programs\VirtualTryOn` ; données séparées dans `%LOCALAPPDATA%\VirtualTryOn`, jamais touchées |
| Compatibilité | Le manifeste porte une `minimum_version` ; en dessous, l'envoi Vinted est bloqué et le bandeau devient obligatoire. `vinted.json` est servi sous un chemin numéroté par format (`data/vinted-v1.json`) |
| Construction | PyInstaller en mode dossier + Inno Setup |
| Signature | Plus tard ; une étape de CI est prévue, désactivée |

Approches écartées : hébergement R2 + Worker dès maintenant (construit l'infrastructure de licence avant sa spec) ; dépôt privé de versions (un jeton dans l'app) ; mise à jour entièrement automatique (version en cours inconnue, échecs invisibles) ; simple lien de téléchargement (trop d'étapes) ; installation dans `Program Files` (UAC à chaque mise à jour) ; PyInstaller en fichier unique (démarrage lent, faux positifs antivirus) ; Nuitka (build long et fragile avec google-genai et pythonnet — gardé en réserve si les antivirus posent problème) ; Briefcase / MSI.

### 1.2 Hors périmètre

- Signature de code (une étape de CI désactivée la prévoit).
- Vérification de licence (sous-projet 5).
- macOS, Linux.
- Canal bêta, mise à jour différentielle, retour à une version antérieure.
- Embarquer un navigateur : Playwright pilote le Chrome (ou Edge) installé, comme aujourd'hui.

## 2. Architecture

### 2.1 Arborescence

```
packaging/
  vto.spec                PyInstaller, mode dossier, sans console
  installer.iss           Inno Setup
  minimum_version.txt     version minimale acceptée, recopiée dans latest.json
  make_manifest.py        génère latest.json (version, minimum, url, sha256, notes)
.github/workflows/
  release.yml             sur tag v* (§5)

backend/src/vto/
  __init__.py             __version__ : source unique de la version
  core/
    paths.py              + install_dir() / is_frozen()
    scenes.py             pack par défaut lu depuis le paquet (§2.3)
    default_scenes/       déplacé depuis la racine du dépôt
  updates/                nouveau paquet ; dépend de core, jamais l'inverse
    manifest.py           lecture et validation de latest.json
    check.py              état : up_to_date | available | required
    install.py            téléchargement, SHA-256, lancement de l'installeur
  api/routes/update.py    GET /api/update, POST /api/update/install, GET /api/update/progress
  desktop.py              + --self-check, + arrêt propre déclenché par la mise à jour
  vinted/remote.py        URL dérivée du numéro de format

frontend/src/components/UpdateBanner.vue
data/vinted-v1.json       renommé depuis data/vinted.json
```

### 2.2 Version

- `vto.__version__` est la seule source. `pyproject.toml` passe en `dynamic = ["version"]` (`[tool.hatch.version] path = "src/vto/__init__.py"`).
- Les versions suivent PEP 440 (`0.2.0`, `0.3.0rc1`) et sont comparées avec `packaging.version.Version` (dépendance ajoutée).
- Le tag `vX.Y.Z` doit être égal à `__version__`, sinon la CI échoue.

### 2.3 Ressources embarquées

Aujourd'hui `scenes.DEFAULT_SCENES_SOURCE` remonte de quatre dossiers depuis le fichier source pour trouver `default_scenes/` à la racine du dépôt : cela casse dans un exécutable comme dans un wheel installé. Le pack est déplacé dans `backend/src/vto/core/default_scenes/` et lu via `importlib.resources.files("vto.core") / "default_scenes"`, comme `vinted.json` l'est déjà via `files("vto.vinted.data")`. Le front compilé (`api/static`) est déjà lu de la même façon.

Le spec PyInstaller embarque explicitement : `vto/api/static`, `vto/vinted/data`, `vto/core/default_scenes`, le pilote Playwright (`playwright/driver`), et utilise les hooks fournis pour pywebview, pythonnet et pydantic.

### 2.4 Installeur Inno Setup

- `AppId` fixe (GUID) ; `PrivilegesRequired=lowest` ; `DefaultDirName={localappdata}\Programs\VirtualTryOn` ; langue française.
- Raccourci menu Démarrer ; raccourci Bureau en tâche optionnelle (cochée par défaut).
- `CloseApplications=yes` et `RestartApplications=no` : l'installeur attend la fermeture de `VirtualTryOn.exe`.
- Fin d'installation : case « Lancer Virtual Try-On » en mode interactif (`postinstall skipifsilent`) ; relance automatique en mode silencieux (entrée `[Run]` avec `Check: WizardSilent`).
- WebView2 : si la clé de registre du runtime est absente, l'installeur exécute le bootstrapper Evergreen de Microsoft embarqué (`/silent /install`, installation par utilisateur possible sans droits administrateur). En cas d'échec : message « Un composant Windows (WebView2) n'a pas pu être installé » et lien vers la page d'aide.
- Désinstallation : supprime le dossier d'installation uniquement ; `%LOCALAPPDATA%\VirtualTryOn` est conservé.

### 2.5 `vinted.json` numéroté

- `data/vinted.json` devient `data/vinted-v1.json` ; la copie embarquée garde son nom.
- `remote.py` construit l'URL à partir de `VintedData.FORMAT` (constante égale au `Literal` du champ `format`) : `…/main/data/vinted-v{FORMAT}.json`. Le cache est nommé de même (`vinted-v1.json`, `vinted-v1.etag`).
- `vto-vinted-catalog` écrit par défaut `data/vinted-v1.json`.
- Aucune version n'est installée chez un client : pas de période de transition pour l'ancien nom.
- Au prochain changement de format, on publie `vinted-v2.json` à côté de `vinted-v1.json`, on maintient le second tant que des versions qui le lisent sont au-dessus de `minimum_version`, puis on relève `minimum_version`.

## 3. Mise à jour

### 3.1 Manifeste `latest.json`

```json
{
  "version": "0.3.0",
  "minimum_version": "0.2.0",
  "url": "https://github.com/Jacques-herrmann/virtual-try-on/releases/download/v0.3.0/VirtualTryOn-Setup-0.3.0.exe",
  "sha256": "…64 caractères hexadécimaux…",
  "notes": "Texte court en français, affiché dans « Nouveautés »."
}
```

- Joint à chaque Release ; lu à l'URL stable `https://github.com/Jacques-herrmann/virtual-try-on/releases/latest/download/latest.json`.
- URL surchargeable par `VTO_UPDATE_URL` (tests, essai, et futur Worker du sous-projet 5). `http://` n'est accepté que vers `127.0.0.1` (manifeste local pour l'essai du bandeau).
- Validé par un modèle pydantic strict ; `url` doit être en `https://`.
- `notes` provient du corps du tag annoté (`git tag -a`), vide sinon.
- Relever `minimum_version` en urgence = publier une version corrective avec `packaging/minimum_version.txt` modifié.

### 3.2 Vérification (`updates.check`)

- Au démarrage, dans un thread, sans bloquer la fenêtre ; puis toutes les 6 h. Délai réseau : 5 s.
- État calculé : `required` si `__version__ < minimum_version`, sinon `available` si `__version__ < version`, sinon `up_to_date`. En cas d'échec réseau ou de manifeste invalide : le dernier état valide est conservé (`unknown` si aucune vérification n'a encore abouti), une ligne dans le log, aucun message au vendeur.
- Gardé en mémoire ; exposé par `GET /api/update` → `{current, latest, status, notes, can_install}`. `can_install` est faux hors exécutable empaqueté (`paths.is_frozen()`).
- `required` est consulté par le service d'envoi Vinted : l'envoi est refusé avec « Cette version ne fonctionne plus avec Vinted. Mets l'application à jour pour envoyer tes annonces. » La génération et la relecture restent disponibles.

### 3.3 Installation (`updates.install`)

`POST /api/update/install` :

1. Refuse (409) si la file de génération n'est pas vide ou si un envoi Vinted tourne : « Une génération est en cours. La mise à jour sera possible quand elle sera terminée. » (ou « Un envoi Vinted est en cours… »).
2. Refuse si `can_install` est faux : « Mise à jour possible uniquement depuis l'application installée. »
3. Télécharge l'installeur dans `cache/updates/` en tâche de fond ; la progression (octets reçus / total) est lue par `GET /api/update/progress`.
4. Compare le SHA-256 au manifeste ; en cas de différence, supprime le fichier et passe en erreur.
5. Lance `VirtualTryOn-Setup-X.Y.Z.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART` détaché (`subprocess.Popen` avec `DETACHED_PROCESS`). Si le lancement échoue (bloqué par l'antivirus), l'app reste ouverte et affiche l'erreur.
6. Demande l'arrêt propre de l'app : arrêt de la file de génération, fermeture du navigateur Vinted piloté, fermeture de la fenêtre pywebview, sortie du processus.

Les anciens installeurs de `cache/updates/` sont supprimés au démarrage suivant (fichiers téléchargés par l'app, pas des données du vendeur).

### 3.4 Bandeau (`UpdateBanner.vue`)

- `available` : bandeau discret « Nouvelle version X disponible » + « Mettre à jour » + « Nouveautés » ; masquable jusqu'au prochain lancement.
- `required` : bandeau rouge, non masquable, « Cette version ne fonctionne plus avec Vinted » + « Mettre à jour ».
- Pendant le téléchargement : barre de progression, bouton désactivé. Puis « Installation… l'application va redémarrer. »
- `can_install` faux : bouton désactivé avec l'explication.

### 3.5 Erreurs

| Cas | Message au vendeur | Log |
|---|---|---|
| Pas de réseau, manifeste illisible | aucun (pas de bandeau) | cause et URL |
| Échec du téléchargement | « Le téléchargement de la mise à jour a échoué. Vérifie ta connexion et réessaie. » | exception httpx |
| SHA-256 différent | « La mise à jour téléchargée est abîmée. Réessaie dans quelques minutes. » | attendu / obtenu |
| Lancement de l'installeur impossible | « Windows a bloqué la mise à jour. Consulte la page d'aide pour l'autoriser. » | OSError |
| Échec pendant l'installation | (Inno annule et restaure les fichiers ; l'ancienne version reste utilisable) | journal Inno `/LOG` dans `logs/` |

## 4. Lancement et test de fumée

`VirtualTryOn.exe --self-check` : importe tous les sous-paquets de `vto`, vérifie la présence et la lisibilité du front compilé, de la copie embarquée de `vinted.json` (validée par le schéma), du pack de scènes par défaut et de l'exécutable du pilote Playwright ; sort avec 0 ou 1. N'ouvre aucune fenêtre ni connexion réseau.

L'exécutable est construit sans console : le résultat est écrit dans le log et dans le fichier passé par `--output`, que la CI lit.

## 5. CI : `release.yml`

Déclenché par un tag `v*`, sur `windows-latest` :

1. Vérifie que le tag (sans `v`) est égal à `vto.__version__`.
2. `npm ci && npm run build` (frontend), `pip install -e backend[dev] pyinstaller`, `ruff check`, `pytest`.
3. `pyinstaller packaging/vto.spec`.
4. `dist/VirtualTryOn/VirtualTryOn.exe --self-check --output selfcheck.txt`.
5. `iscc packaging/installer.iss` (Inno Setup installé via `choco install innosetup` s'il n'est pas sur l'image).
6. Étape de signature : présente, désactivée (`if: false`), prévue pour signer l'exécutable puis l'installeur.
7. Installation silencieuse dans un dossier temporaire (`/DIR=`), `--self-check` sur l'app installée, désinstallation silencieuse ; vérifie qu'un fichier témoin placé dans `VTO_DATA_DIR` a survécu.
8. `python packaging/make_manifest.py` → `latest.json`.
9. Crée une Release GitHub **en brouillon** avec l'installeur et `latest.json`. La publication est manuelle, après essai : une Release brouillon n'est pas servie par `releases/latest`.

## 6. Tests

Sans réseau, `httpx.MockTransport` pour le serveur, faux lanceur de processus :

- `manifest` : valide, champ manquant, `url` en http, JSON invalide, délai dépassé.
- `check` : comparaisons PEP 440 (y compris préversions), les trois états, `unknown` en cas d'échec.
- `install` : empreinte bonne / mauvaise (fichier supprimé), refus si occupé, refus hors exécutable, arguments de l'installeur, arrêt demandé seulement après lancement réussi, nettoyage de `cache/updates/`.
- API `/api/update*` : codes et messages.
- Service d'envoi Vinted : refus en état `required`.
- `remote` : URL dérivée du format, noms du cache.
- `scenes` : pack par défaut trouvé via `importlib.resources`.
- `--self-check` : succès dans l'environnement de dev ; échec si une ressource manque.
- Front (Vitest) : bandeau dans chaque état, progression, erreur.

## 7. Acceptation manuelle

Installation sur une machine vierge : le PC d'un ami (étapes 1-2). Mises à jour et désinstallation : sur le poste de l'utilisateur (étapes 3-5).

1. Publier `v0.2.0`, l'installer : pas d'UAC ; noter l'avertissement SmartScreen pour la page d'aide.
2. Saisir la clé Gemini, générer un article, se connecter à Vinted, créer un brouillon.
3. Publier `v0.2.1` : le bandeau apparaît ; mise à jour en un clic ; l'app redémarre en 0.2.1, articles et session Vinted intacts.
4. Passer `minimum_version.txt` à `0.2.2`, publier `v0.2.2`, relancer une app en 0.2.1 : bandeau rouge, envoi Vinted refusé, génération possible.
5. Désinstaller : `%LOCALAPPDATA%\VirtualTryOn` est conservé.

## 8. Documentation

- `CLAUDE.md` : commandes de build local (`pyinstaller packaging/vto.spec`, `iscc packaging/installer.iss`), procédure de publication (bump de `__version__`, tag annoté avec les notes, essai du brouillon, publication), nouveau chemin du pack de scènes et de `vinted-v1.json`.
- Page d'aide (dans le dépôt, `docs/aide/installation.md`) : avertissement SmartScreen (« Informations complémentaires » → « Exécuter quand même »), antivirus, WebView2.
