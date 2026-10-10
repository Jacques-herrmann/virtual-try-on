# Sous-projet 2 — App (API + UI desktop) — Design

Date : 2026-10-10
Statut : validé en brainstorming, en attente de relecture

## 1. Contexte

Le sous-projet 1 a livré le cœur `vto.core` (stockage des articles, scènes, génération Gemini, pipeline) et une CLI de développement. Ce sous-projet ajoute l'application utilisée par le client final : une API FastAPI locale et une UI Vue affichée dans une fenêtre `pywebview`.

### 1.1 Décisions (prises en brainstorming)

| Sujet | Décision |
|---|---|
| Déroulé de travail | File de génération en arrière-plan : chaque article saisi part dans la file, le vendeur continue de saisir. Couvre le travail « au fil de l'eau » comme « par lot » |
| Relecture (v1) | Modifier l'annonce, régénérer une image ou toutes, régénérer l'annonce seule, écarter une image, valider |
| Scènes | Gestion complète dans l'UI : créer, renommer, activer, ordonner, éditer le prompt, ajouter/supprimer des décors (par sous-dossier), supprimer une scène |
| Premier lancement | Écran d'accueil guidé obligatoire tant qu'aucune clé valide n'est enregistrée, avec vérification de la clé |
| Photos | Glisser-déposer et sélecteur de fichiers uniquement |
| Organisation | Écran principal en deux colonnes (liste des articles / détail), barre latérale Articles · Scènes · Réglages |
| Suivi de la génération | Interrogation régulière de l'API (polling), pas de SSE ni de pont `js_api` |
| Composants UI | Vue 3 + Vite + TypeScript + vue-router + PrimeVue |

### 1.2 Hors périmètre

- Envoi sur Vinted, ordre des photos, inclusion des photos d'origine (sous-projet 3).
- Packaging PyInstaller, installeur (sous-projet 4).
- Envoi des photos depuis le téléphone, dossier surveillé.
- Enregistrement en brouillon sans générer.
- Génération de plusieurs articles en parallèle.
- Tests E2E du front.

## 2. Architecture

### 2.1 Arborescence

```
backend/src/vto/
  core/            existant, complété (§3)
  api/
    app.py         create_app(...) : FastAPI, routes, statiques, sécurité
    security.py    jeton de session (cookie) + contrôle du Host
    queue.py       GenerationQueue
    routes/
      articles.py
      scenes.py
      settings.py
      files.py
      system.py
    static/        front compilé (ignoré par git, produit par `npm run build`)
  desktop.py       point d'entrée `vto-app`
frontend/          Vue 3 + Vite + TypeScript + vue-router + PrimeVue
```

`npm run build` écrit dans `backend/src/vto/api/static/`.

### 2.2 Dépendances

`desktop` → `api` → `core`. `core` n'importe jamais `api` ni `desktop`.

`create_app(client_factory, …)` reçoit une fabrique `clé -> GenAIClient` (`pipeline.ClientFactory`, par défaut `GeminiClient`) : les tests injectent `FakeClient`. La même fabrique sert à la file (via `pipeline.build_client(settings, client_factory)`) et à la vérification de clé.

### 2.3 Sécurité de l'API locale

- Le serveur écoute uniquement sur `127.0.0.1`, sur un port libre choisi au lancement.
- `desktop.py` génère un jeton aléatoire (`secrets.token_urlsafe(32)`) et ouvre la fenêtre sur `http://127.0.0.1:<port>/?token=<jeton>`.
- `GET /` avec le bon jeton pose un cookie `vto_session` (`HttpOnly; SameSite=Strict; Path=/`) puis redirige vers `/`. Un cookie plutôt qu'un en-tête, car les balises `<img>` ne peuvent pas envoyer d'en-tête.
- Toutes les routes `/api/*` et `/files/*` exigent ce cookie (sinon 401).
- Toute requête dont l'en-tête `Host` diffère de `127.0.0.1:<port>` est refusée (400), pour bloquer le DNS rebinding.
- Mode dev (`vto-app --dev`) : API seule sur un port fixe (8765), jeton fixe `dev`. Le serveur Vite (proxy vers l'API) sert le front.

## 3. Changements dans le cœur

### 3.1 `models.py`

- Nouveau statut `ArticleStatus.QUEUED = "queued"`.
- Nouveau modèle :

  ```python
  class GenerationJob(BaseModel):
      scene_slugs: list[str] | None = None   # None = toutes les scènes actives
      regenerate_listing: bool = False
      queued_at: datetime
  ```

- `Article.job: GenerationJob | None = None` : demande en attente, persistée pour reconstruire la file après un redémarrage.
- `SceneResult.excluded: bool = False` : image écartée par le vendeur. Une régénération de la scène produit un nouveau `SceneResult`, donc `excluded=False`.

### 3.2 `storage.py`

Transitions (nouvelles en gras) :

| De | Vers |
|---|---|
| DRAFT | **QUEUED**, GENERATING |
| **QUEUED** | **GENERATING**, **DRAFT**, **TO_REVIEW** (annulation avant démarrage) |
| GENERATING | TO_REVIEW, ERROR, DRAFT, **QUEUED** (reprise après plantage) |
| TO_REVIEW | GENERATING, VALIDATED, **QUEUED** |
| ERROR | GENERATING, **QUEUED** |
| VALIDATED | TO_REVIEW, PUBLISHED |
| PUBLISHED | — |

`DRAFT → GENERATING` et `TO_REVIEW/ERROR → GENERATING` restent autorisées pour la CLI.

Nouvelles fonctions :

- `enqueue(article, job)` : enregistre `job` et passe en `QUEUED`.
- `cancel_queued(article)` : efface `job` et revient à `TO_REVIEW` si l'article a déjà une image `ok` ou une annonce, sinon à `DRAFT`.
- `update_input(article, user_input)` : interdit en `QUEUED`, `GENERATING` et `PUBLISHED` (`VtoError` avec message explicite).
- `update_listing(article, listing)` et `set_excluded(article, slug, excluded)` : autorisés uniquement en `TO_REVIEW`.
- `recover_interrupted()` : passe les articles `GENERATING` en `QUEUED` en leur donnant un `job` complet (toutes scènes) s'ils n'en ont pas, et renvoie la liste des articles `QUEUED` triés par `job.queued_at`.

Les refus utilisent des `VtoError` avec un message en français.

### 3.3 `pipeline.py`

- `process_article` accepte un article `QUEUED` : `article.job` remplace alors les paramètres `scene_slugs`/`regenerate_listing` (que la CLI continue d'utiliser pour les articles hors file). Une scène de `job` supprimée ou désactivée entre-temps est ignorée (avertissement dans le log) plutôt que de bloquer l'article. `job` n'est effacé qu'à la fin du traitement (succès, erreur ou annulation) : si l'app est fermée en pleine génération, l'article reste `GENERATING` avec son `job` et `recover_interrupted` le reprend à l'identique (une régénération d'une seule scène ne devient pas une régénération complète).
- Annulation pendant le traitement : `_finish_cancelled` inchangé (`TO_REVIEW` ou `DRAFT`).

### 3.4 `scenes.py`

- `SceneInfo` (dataclass) : `slug`, `name`, `enabled`, `order`, `problem: str | None` (« aucun décor », « prompt.md manquant », « meta.json invalide »).
- `list_scene_infos()` : toutes les scènes, y compris inutilisables, pour l'UI. `list_scenes()` reste inchangé pour le pipeline.
- `create_scene(name) -> SceneInfo` : slug dérivé du nom (minuscules, sans accents, tirets), rendu unique par suffixe `-2`, `-3`… ; crée `prompt.md` à partir d'un modèle (`vto/core/prompts/scene_template.md`), `meta.json` (`order` = dernier + 1) et `backgrounds/`.
- `update_scene(slug, *, name=None, enabled=None, order=None, prompt=None)`.
- `delete_scene(slug)` : suppression explicite du dossier entier.
- `list_backgrounds(slug) -> list[str]` : chemins relatifs à `backgrounds/` (`robe/01.jpg`, `fond.png`).
- `add_background(slug, source: Path, subfolder: str | None) -> str` : `subfolder` doit être un `GarmentType`, un `Audience` ou `None` (racine) ; nom de fichier conservé, suffixé en cas de collision ; renvoie le chemin relatif.
- `delete_background(slug, rel_path)`.
- Tout chemin reçu (slug, `rel_path`) est résolu puis vérifié comme étant sous le dossier attendu ; sinon `VtoError`.

### 3.5 Vérification de clé

- `GenAIClient.check_models(models: Sequence[str]) -> None` : appel de métadonnées du SDK (`models.get`) pour chaque modèle, sans génération. Erreurs traduites par `map_sdk_error` (`InvalidApiKey`, `ProjectBlocked`, `ModelUnavailable`, `TransientError`). L'appel SDK exact est confirmé à l'implémentation et couvert par le test `live`.
- `FakeClient.check_models` : configurable pour lever une erreur donnée.
- `pipeline.verify_api_key(key, settings, client_factory)` : construit un client avec `key` (pas la clé effective des réglages, que `GEMINI_API_KEY` peut surcharger) et vérifie `image_model` et `text_model`.

## 4. API

### 4.1 `GenerationQueue` (`api/queue.py`)

- Un thread démon, une `deque` d'identifiants, un `threading.Condition`.
- `start()` : appelle `storage.recover_interrupted()` et remplit la file.
- `enqueue(article_id, job)` : `storage.enqueue` puis ajout en fin de file.
- `cancel(article_id)` : si en attente, retrait + `storage.cancel_queued` ; si en cours, déclenche l'`Event` d'annulation passé au pipeline.
- Traitement : pour chaque article, crée le client via `build_client(load_settings(), client_factory)` (une nouvelle clé est donc prise en compte immédiatement) puis appelle `process_article`.
- Sur `FATAL` (clé manquante/invalide, quota) : la file se met en **pause** (`paused=True`, `reason=user_message`), l'article concerné passe en `ERROR` (comportement actuel du pipeline), les suivants restent `QUEUED`.
- `resume()` : lève la pause. Un enregistrement de clé valide (`check-key`) appelle `resume()`.
- `status() -> {running: str | None, pending: list[str], paused: bool, reason: str | None}`.
- `stop()` : n'accepte plus de travail ; le thread démon s'arrête avec le processus. L'article en cours n'est pas annulé : il reste `GENERATING` avec son `job` et sera repris au lancement suivant.
- La fonction de traitement est injectable (`process=pipeline.process_article`) pour des tests déterministes.

### 4.2 Routes

Préfixe `/api`, JSON. Erreur : `{"message": "<texte pour le client>"}`.

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/articles?status=` | liste, du plus récent au plus ancien |
| POST | `/articles` | multipart : `photos[]` + champs `UserInput` ; crée l'article et le met en file (toutes scènes + annonce) |
| GET | `/articles/{id}` | détail |
| PATCH | `/articles/{id}/input` | corrige la saisie |
| PATCH | `/articles/{id}/listing` | modifie l'annonce |
| POST | `/articles/{id}/generate` | `{scenes?: list[str], listing?: bool}` ; sans corps = tout régénérer |
| POST | `/articles/{id}/cancel` | annule (en attente ou en cours) |
| PATCH | `/articles/{id}/scenes/{slug}` | `{excluded: bool}` |
| POST | `/articles/{id}/validate` | `TO_REVIEW → VALIDATED` |
| POST | `/articles/{id}/unvalidate` | `VALIDATED → TO_REVIEW` |
| DELETE | `/articles/{id}` | suppression explicite ; refusée en `QUEUED`/`GENERATING` |
| GET | `/health` | `{"ok": true}`, sans cookie, sans donnée (attente du démarrage par `desktop.py`) |
| GET | `/queue` | `GenerationQueue.status()` |
| POST | `/queue/resume` | lève la pause |
| GET | `/settings` | réglages sans la clé : `has_key`, `key_hint` (4 derniers caractères) |
| PUT | `/settings` | `signature`, `listing_prompt`, `image_model`, `text_model` |
| POST | `/settings/reset-listing-prompt` | rétablit le prompt par défaut |
| POST | `/settings/check-key` | `{key}` : vérifie, enregistre si valide, relance la file |
| GET | `/scenes` | `list_scene_infos()` |
| POST | `/scenes` | `{name}` |
| GET | `/scenes/{slug}` | infos + prompt + décors |
| PATCH | `/scenes/{slug}` | `{name?, enabled?, order?, prompt?}` |
| DELETE | `/scenes/{slug}` | suppression explicite |
| POST | `/scenes/{slug}/backgrounds` | multipart : `files[]` + `subfolder?` |
| DELETE | `/scenes/{slug}/backgrounds/{path:path}` | suppression explicite d'un décor |
| POST | `/system/open-logs` | ouvre le dossier des logs (`os.startfile`) ; aucun chemin fourni par le client |

Fichiers (même cookie requis) :

- `GET /files/articles/{id}/{path:path}` : photos et images générées.
- `GET /files/scenes/{slug}/{path:path}` : décors.

Chemins résolus et vérifiés comme étant sous le dossier de l'article ou de la scène.

### 4.3 Uploads

- Extensions acceptées : celles reconnues par `images.is_supported_image`.
- 30 Mo maximum par fichier ; au moins une photo par article.
- Fichiers reçus écrits dans un dossier temporaire puis passés au cœur (`create_article`, `add_background`), qui copie.

### 4.4 Erreurs

| Exception | HTTP |
|---|---|
| `ArticleNotFound` | 404 |
| `InvalidTransition` | 409 |
| autre `VtoError` | 400 |
| validation FastAPI | 422, message générique en français |
| exception inattendue | 500, message générique ; trace dans le log |

## 5. Lancement (`vto-app`)

Script déclaré dans `pyproject.toml` : `vto-app = "vto.desktop:main"`.

1. `setup_logging()`, `ensure_default_scenes()`.
2. Création de `GenerationQueue`, `start()`.
3. uvicorn dans un thread sur `127.0.0.1:<port libre>`, attente qu'il réponde.
4. `webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True` ; fenêtre « Virtual Try-On », 1280×800, redimensionnable, minimum 1024×700.
5. Si `api/static/index.html` est absent, `GET /` renvoie une page expliquant de lancer `npm run build`.
6. Fermeture de la fenêtre : `queue.stop()`, arrêt d'uvicorn, fin du processus. L'article en cours et les articles en attente sont repris au lancement suivant (§3.2 `recover_interrupted`).

Nouvelles dépendances Python : `fastapi`, `uvicorn`, `python-multipart`, `pywebview` ; en dev : `httpx` (déjà présent via le SDK) pour `TestClient`.

## 6. UI

### 6.1 Structure du front

```
frontend/src/
  api.ts             client fetch typé ; erreurs → notification avec `message`
  types.ts           miroir des modèles (Article, Listing, SceneInfo…)
  router.ts          /welcome, /articles/:id?, /scenes/:slug?, /settings
  stores/            état partagé en composables (articles + file, réglages)
  views/             WelcomeView, ArticlesView, ScenesView, SettingsView
  components/        ArticleList, ArticleForm, ArticleProgress, ArticleReview,
                     PhotoDrop, SceneEditor, BackgroundGallery, QueueBanner
```

Langue : français, tutoiement (comme les messages du cœur). Locale PrimeVue en français.

### 6.2 Accueil

Affiché tant que `has_key` est faux. Trois étapes : ouvrir Google AI Studio (lien externe), créer une clé, la coller. Bouton « Vérifier » → `check-key` ; erreur affichée sous le champ ; succès → écran principal.

### 6.3 Articles (écran principal)

- **Barre latérale** : Articles · Scènes · Réglages.
- **Colonne gauche** : bouton « + Nouvel article » ; filtres Tous / En cours (`queued` + `generating`) / À relire / Validés / Erreur, avec compteurs ; une ligne par article (vignette de la première photo, type, titre de l'annonce s'il existe, pastille de statut). `QueueBanner` au-dessus : « Génération en pause : <raison> » + « Reprendre ».
- **Colonne droite**, selon le statut :
  - *Nouvel article / brouillon* : `PhotoDrop` (aperçus, retrait), type obligatoire, champs facultatifs (public, marque, taille, état, couleur, prix, notes). « Générer » crée l'article puis vide le formulaire pour la saisie suivante.
  - *En attente / en cours* : photo d'origine ; une case par scène (« en attente » puis l'image) ; « Annuler ».
  - *À relire* : grille des images (« Régénérer », « Écarter » / « Reprendre » par image, « Tout régénérer ») ; formulaire de l'annonce modifiable (enregistrement explicite) ; « Régénérer l'annonce » (confirmation : le texte actuel sera remplacé) ; « Modifier la saisie » ; « Valider ».
  - *Validé* : même vue en lecture seule ; « Repasser en relecture ».
  - *Erreur* : message, résultats partiels, « Réessayer ».
- Suppression d'un article : bouton dans le détail, confirmation obligatoire.
- **Rafraîchissement** : `GET /api/articles` et `GET /api/queue` toutes les 1,5 s tant qu'au moins un article est `queued` ou `generating` ; arrêt sinon (reprise dès qu'une action en met un en file).

### 6.4 Scènes

- Liste : nom, interrupteur actif/inactif, flèches d'ordre, badge si `problem`.
- Détail : nom, éditeur du prompt (rappel de la variable `{garment_type}`), `BackgroundGallery` regroupée par sous-dossier (« Tous types » = racine, puis chaque type ou public), ajout par glisser-déposer avec choix du sous-dossier, suppression avec confirmation.
- « Nouvelle scène » ; « Supprimer la scène » avec confirmation indiquant le nombre de décors supprimés.

### 6.5 Réglages

Clé (masquée, `key_hint`, « Changer » → revérification) ; signature ; prompt d'annonce + « Rétablir le texte par défaut » ; section « Avancé » : modèle image, modèle texte ; « Ouvrir le dossier des logs ».

### 6.6 Erreurs côté front

Chaque appel passe par `api.ts` : en cas d'erreur, notification avec `message`. Si l'API ne répond plus (erreur réseau), bandeau permanent « L'application ne répond plus. Ferme-la et relance-la. ».

## 7. Tests

Aucun test n'appelle le réseau (sauf `-m live`).

- **Cœur** : nouvelles transitions ; `enqueue`, `cancel_queued`, `recover_interrupted` ; `update_input`/`update_listing`/`set_excluded` et leurs refus ; `process_article` depuis `QUEUED` avec `job` ; CRUD des scènes, slugs uniques, refus des chemins hors dossier ; `check_models` avec SDK factice ; test `live` de `check_models`.
- **File** : traitement injecté, sans `sleep` réel : ordre FIFO, annulation en attente et en cours, pause sur `FATAL` puis reprise, reconstruction au démarrage.
- **API** (`TestClient`, `FakeClient`, `VTO_DATA_DIR` temporaire) : parcours création → file → `to_review` → modification de l'annonce → exclusion → validation ; régénération d'une scène ; annulation ; pause sur clé invalide puis `check-key` qui relance ; CRUD scènes et décors ; rejet sans cookie (401) et avec un `Host` étranger (400) ; uploads invalides (extension, taille, aucune photo) ; codes d'erreur du §4.4 ; la clé n'apparaît jamais dans `GET /settings`.
- **Front** (Vitest) : `api.ts` (erreurs, réseau coupé), choix du panneau selon le statut, arrêt/reprise du rafraîchissement.
- **CI** : job `frontend` (`npm ci`, `npm run build`, `npm test`) en plus du job Python existant.

## 8. Critères d'acceptation

- `pytest backend/tests`, `ruff check backend` et `npm test` passent ; la CI est verte.
- `vto-app` démarre sur une installation vierge (`VTO_DATA_DIR` vide) : écran d'accueil, clé vérifiée, scènes par défaut présentes.
- Essai manuel : 3 vrais articles saisis à la suite pendant que la file tourne ; relecture (une image régénérée, une écartée, annonce modifiée) ; validation des 3.
- Fermer l'app pendant une génération puis la relancer : les articles en attente sont repris.
- Création d'une scène avec deux décors (un à la racine, un dans `robe/`) utilisée lors d'une génération.
