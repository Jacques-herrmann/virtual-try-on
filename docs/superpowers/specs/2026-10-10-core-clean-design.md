# Sous-projet 1 — Cœur propre (« soft clean ») — Design

Date : 2026-10-10
Statut : validé en brainstorming, en attente de relecture

## 1. Contexte

Le dépôt contient un prototype personnel qui :

1. génère, pour chaque vêtement, deux photos « portées » (mannequin, cintre) via Gemini à partir d'une photo du vêtement et d'un décor ;
2. génère une annonce Vinted (titre, description, prix…) via Gemini ;
3. crée des brouillons Vinted par automatisation Selenium (`create_post.py`).

Objectif global : en faire un produit vendable à des vendeurs Vinted non techniques.

### 1.1 Décisions produit (prises en brainstorming)

| Sujet | Décision |
|---|---|
| Cible | Vendeurs non techniques ; application desktop Windows d'abord, SaaS possible plus tard |
| Clé Gemini | Fournie par le client (BYOK), saisie dans les réglages |
| Automatisation Vinted | Conservée comme fonctionnalité phare, à fiabiliser |
| Décors | Pack de scènes fourni + scènes du client ; prompts modifiables par le client |
| Saisie des vêtements | Dans l'app, article par article (glisser-déposer + champs facultatifs) |
| Relecture | Écran de relecture obligatoire avant envoi sur Vinted (régénérer une image, éditer l'annonce, valider) |
| Stack app | Backend Python (FastAPI) + UI Vue/Vite dans une fenêtre `pywebview`, packagé PyInstaller |
| Session Vinted | Profil Chrome persistant dédié, connexion manuelle par le client ; aucun mot de passe stocké |
| Mises à jour | Installeur Inno Setup + mise à jour en un clic ; sélecteurs Vinted dans un JSON distant (données uniquement, jamais de code) |
| Licence | Achat unique perpétuel incluant 12 mois de mises à jour + abonnement annuel optionnel aux mises à jour ; plateforme *merchant of record* ; petit service (ex. Cloudflare Worker) qui vérifie la licence avant de servir mises à jour et sélecteurs ; anti-piratage volontairement léger |

### 1.2 Découpage en sous-projets

| # | Sous-projet | Dépend de |
|---|---|---|
| **1** | **Cœur propre** (ce document) | — |
| 2 | App : API FastAPI + UI Vue + fenêtre `pywebview` | 1 |
| 3 | Vinted : profil persistant, sélecteurs distants, remplissage complet du formulaire | 1 |
| 4 | Distribution : PyInstaller, Inno Setup, mises à jour | 2, 3 |
| 5 | Licence : module `licensing` + Worker + plateforme de paiement | 4 |

Chaque sous-projet a son propre cycle spec → plan → implémentation. Seul le sous-projet 1 est spécifié ici.

## 2. Périmètre du sous-projet 1

**Inclus**

- Package Python `vto` installable (`pyproject.toml`), sans secret ni chemin codé en dur.
- Configuration et chemins des données utilisateur.
- Modèles de données, stockage des articles, cycle de statuts.
- Scènes (décors + prompt modifiable).
- Génération d'images et d'annonce, avec retries et erreurs explicites.
- Pipeline de traitement d'un article, annulable.
- CLI de développement.
- Script d'import des données du prototype.
- Tests pytest + CI GitHub Actions (pytest + ruff).
- Déplacement de `create_post.py` dans `legacy/`, suppression des autres fichiers du prototype.

**Exclus** : API HTTP, UI, automatisation Vinted (hors déplacement en `legacy/`), packaging, mises à jour, licence.

## 3. Architecture

### 3.1 Arborescence du dépôt

```
virtual-try-on/
├─ backend/
│  ├─ pyproject.toml
│  ├─ src/vto/
│  │  ├─ core/
│  │  │  ├─ config.py
│  │  │  ├─ paths.py
│  │  │  ├─ models.py
│  │  │  ├─ storage.py
│  │  │  ├─ images.py
│  │  │  ├─ scenes.py
│  │  │  ├─ errors.py
│  │  │  ├─ generation/
│  │  │  │  ├─ client.py
│  │  │  │  ├─ image.py
│  │  │  │  └─ listing.py
│  │  │  └─ pipeline.py
│  │  ├─ cli.py
│  │  └─ tools/import_legacy.py
│  └─ tests/
├─ default_scenes/
│  ├─ mannequin/
│  └─ cintre/
├─ legacy/create_post.py
└─ .github/workflows/ci.yml
```

Les dossiers `vinted/`, `api/`, `licensing/`, `updates/` et `frontend/` seront créés par les sous-projets suivants.

### 3.2 Règle de dépendance

`vto.core` n'importe rien de `vto.cli`, `vto.tools`, ni des futurs `vto.api`, `vto.vinted`, `vto.licensing`, `vto.updates`. Toute dépendance va vers `core`, jamais l'inverse. Le CLI est une interface parmi d'autres posée sur le cœur.

### 3.3 Données utilisateur

Racine : `%APPDATA%\VirtualTryOn\` sous Windows (`platformdirs.user_data_dir`), surchargeable par la variable d'environnement `VTO_DATA_DIR` (tests, développement).

```
<racine>/
├─ settings.json
├─ scenes/<slug>/
│  ├─ meta.json
│  ├─ prompt.md
│  └─ backgrounds/
│     ├─ *.jpg|png|webp|avif
│     └─ <garment_type>/*.jpg…        (facultatif)
└─ articles/<id>/
   ├─ article.json
   ├─ photos/
   └─ generated/<scene_slug>.jpg
```

Au premier lancement, si `scenes/` est vide, `default_scenes/` y est copié. Les scènes copiées appartiennent ensuite au client et ne sont jamais écrasées.

## 4. Composants

### 4.1 `paths.py`

Calcule tous les chemins à partir de la racine (`data_dir()`, `scenes_dir()`, `articles_dir()`, `article_dir(id)`, `settings_file()`). Aucun autre module ne construit de chemin vers les données utilisateur.

### 4.2 `config.py` — `Settings`

Modèle pydantic chargé/sauvé dans `settings.json`.

| Champ | Type | Défaut |
|---|---|---|
| `gemini_api_key` | `str \| None` | `None` |
| `image_model` | `str` | modèle image Gemini courant, vérifié à l'implémentation |
| `text_model` | `str` | modèle texte Gemini courant, vérifié à l'implémentation (remplace `gemini-2.0-flash`) |
| `listing_prompt` | `str` | prompt actuel de `description.py`, sans le rappel de promo |
| `signature` | `str` | `""` (le rappel de promo du prototype n'est pas un défaut produit ; il est importé par le script de migration) |

`gemini_api_key` peut aussi venir de la variable d'environnement `GEMINI_API_KEY`, qui est prioritaire (développement, CI live).

### 4.3 `models.py`

```python
GarmentType = Literal["haut", "robe", "jupe", "pantalon", "veste", "chaussures", "sac", "accessoire", "autre"]

class ArticleStatus(StrEnum):
    DRAFT = "draft"              # saisi, pas encore généré
    GENERATING = "generating"
    TO_REVIEW = "to_review"      # généré (éventuellement partiellement) ; à relire
    VALIDATED = "validated"      # relu et validé par le client
    PUBLISHED = "published"      # brouillon Vinted créé (sous-projet 3)
    ERROR = "error"              # échec bloquant (aucune image, annonce impossible)

class UserInput(BaseModel):      # saisi par le client, tout facultatif sauf type
    garment_type: GarmentType
    brand: str | None
    size: str | None
    condition: str | None
    color: str | None
    price: float | None
    notes: str | None

class Listing(BaseModel):        # schéma imposé à Gemini (sortie structurée)
    title: str
    description: str
    category: str | None
    brand: str | None
    size: str | None
    condition: Literal["Neuf", "Comme neuf", "Très bon état", "Bon état", "Satisfaisant"] | None
    color: str | None
    price: float | None
    parcel_size: Literal["Petit", "Moyen", "Grand"] | None

class SceneResult(BaseModel):
    scene: str                   # slug
    status: Literal["pending", "ok", "error"]
    image: str | None            # chemin relatif à l'article
    error: str | None

class Article(BaseModel):
    id: str                      # ULID/uuid4
    created_at: datetime
    status: ArticleStatus
    input: UserInput
    photos: list[str]            # chemins relatifs, ordre = ordre d'import
    scenes: list[SceneResult]
    listing: Listing | None
    error: str | None
```

Les valeurs de `condition` reprennent les libellés Vinted ; la liste est vérifiée à l'implémentation et ajustée si Vinted a changé.

### 4.4 `storage.py`

- `create_article(input, photo_paths) -> Article` : crée le dossier, copie les photos dans `photos/`, écrit `article.json` en statut `DRAFT`.
- `load(id)`, `save(article)`, `list_articles()`, `delete(id)`.
- Écriture atomique de `article.json` (fichier temporaire puis `os.replace`).
- `set_status(article, new)` refuse les transitions non autorisées (`InvalidTransition`) :

```
DRAFT → GENERATING
GENERATING → TO_REVIEW | ERROR | DRAFT (annulation)
TO_REVIEW → GENERATING (régénération) | VALIDATED
ERROR → GENERATING
VALIDATED → TO_REVIEW (dévalidation) | PUBLISHED
```

Les dossiers d'articles ne sont jamais supprimés implicitement.

### 4.5 `images.py`

Reprend `utils.py` : chargement PIL avec `exif_transpose`, conversion RGB, redimensionnement (côté max 1536 px), support AVIF via `pillow-avif-plugin` si Pillow ne le gère pas nativement.

### 4.6 `scenes.py`

- `Scene` : `slug`, `name`, `enabled`, `order`, `prompt` (contenu de `prompt.md`), `backgrounds_dir`.
- `meta.json` : `{"name": str, "enabled": bool, "order": int}`.
- `list_scenes(enabled_only=True)` triées par `order`. Un dossier sans `prompt.md` ou sans décor est ignoré et signalé en log.
- `pick_background(scene, garment_type, rng)` : tire au hasard dans `backgrounds/<garment_type>/` s'il existe et contient des images, sinon dans les images à la racine de `backgrounds/`. Lève `NoBackground` si rien.
- `render_prompt(scene, garment_type)` : remplace `{garment_type}`. Aucune autre variable.
- `ensure_default_scenes()` : copie `default_scenes/` si `scenes/` est vide.

Pack par défaut : `mannequin` (order 1, prompt = `PROMPT_DUMMY` actuel) et `cintre` (order 2, prompt = `PROMPT_HANGER` actuel), décors issus des dossiers du prototype. Les deux prompts sont retouchés pour retirer la consigne de format en majuscules si l'API permet d'imposer le ratio (cf. 4.7).

### 4.7 `generation/`

**`client.py`**

```python
class GenAIClient(Protocol):
    def generate_image(self, model: str, prompt: str, images: list[Image]) -> bytes: ...
    def generate_json(self, model: str, prompt: str, images: list[Image], schema: type[BaseModel]) -> BaseModel: ...
```

- `GeminiClient` implémente ce protocole avec `google-genai`. Clé passée au constructeur.
- Ratio 3:4 imposé via le paramètre de configuration d'image de l'API s'il existe pour le modèle choisi ; sinon la consigne reste dans le prompt.
- `generate_json` utilise la sortie structurée (`response_mime_type="application/json"`, `response_schema=schema`) et valide la réponse avec pydantic.
- Traduction des erreurs SDK en exceptions du cœur (`errors.py`) :
  - `InvalidApiKey`, `QuotaExceeded`, `ModelUnavailable` → définitives ou explicites ;
  - `TransientError` (429 hors quota épuisé, 5xx, timeout réseau) → retentée ;
  - `NoImageReturned`, `InvalidModelOutput`.
- Retry : 3 tentatives max sur `TransientError` et `NoImageReturned`, backoff exponentiel (2 s, 4 s, 8 s) avec jitter. Aucune nouvelle tentative sur les erreurs définitives.

**`image.py`** — `generate_scene_image(client, settings, scene, article, garment_photo) -> Path`

- Décor via `pick_background`, prompt via `render_prompt`.
- Ordre envoyé au modèle : prompt, décor ([Image A]), vêtement ([Image B]) — identique au prototype.
- Photo du vêtement : première photo de l'article.
- Sauvegarde en `generated/<slug>.jpg` (JPEG qualité 95).

**`listing.py`** — `generate_listing(client, settings, article) -> Listing`

- Entrées : `settings.listing_prompt`, première image générée disponible (sinon photo d'origine), photo d'origine, et un bloc « Informations connues » construit depuis `UserInput` (champs non nuls + notes).
- Le prompt demande `null` pour toute information inconnue (plus de `[x]`).
- Après réponse : chaque champ renseigné dans `UserInput` écrase le champ correspondant de `Listing` (marque, taille, état, couleur, prix).
- `signature` non vide → ajoutée à la fin de `description`, séparée par une ligne vide.

### 4.8 `pipeline.py`

`process_article(article_id, *, client, settings, scenes=None, cancel: threading.Event | None, on_progress: Callable | None)`

1. Statut `GENERATING`.
2. Pour chaque scène active (ou la liste `scenes` passée, pour régénérer une seule image) : `generate_scene_image`. Échec → `SceneResult(status="error", error=message lisible)`, on continue avec la scène suivante. Sauvegarde de l'article après chaque scène.
3. Annonce : générée si elle n'existe pas encore (une régénération d'image ne régénère pas l'annonce ; `regenerate_listing(article_id)` est une fonction séparée).
4. Statut final :
   - au moins une image OK et annonce OK → `TO_REVIEW` (les scènes en erreur sont visibles dans l'article) ;
   - aucune image OK, ou annonce impossible → `ERROR` avec message.
5. Annulation (`cancel` positionné) : vérifiée entre deux appels API ; l'article revient en `DRAFT` s'il n'avait rien de généré, sinon en `TO_REVIEW`.
6. `InvalidApiKey` / `QuotaExceeded` : arrêt immédiat du lot entier (inutile d'enchaîner les échecs), article en `ERROR`, exception propagée à l'appelant.

`process_batch(article_ids, …)` traite séquentiellement.

`on_progress(article_id, step, detail)` permet au futur UI d'afficher l'avancement ; le CLI l'utilise pour afficher des lignes de log.

### 4.9 Messages d'erreur

Chaque exception du cœur porte un message en français destiné au client final, par exemple :

- `InvalidApiKey` : « Ta clé Gemini est invalide. Vérifie-la dans les réglages. »
- `QuotaExceeded` : « Quota Gemini atteint. Réessaie plus tard ou vérifie ton forfait Google AI. »
- `NoBackground` : « La scène « {name} » n'a aucun décor pour le type « {type} ». »

Les traces techniques vont dans un fichier de log (`<racine>/logs/vto.log`, rotation), pas dans les messages.

## 5. CLI de développement (`vto`)

Point d'entrée déclaré dans `pyproject.toml`.

```
vto config set-key <clé>                     # écrit gemini_api_key dans settings.json
vto add <photo>... --type robe [--brand Zara] [--size M] [--notes "..."]
vto list                                     # id, statut, type, titre
vto run [<id>...]                            # traite les articles DRAFT (ou ceux passés)
vto regen <id> [--scene mannequin] [--listing]
vto show <id>                                # affiche l'annonce et les chemins des images
vto export <id> <dossier>                    # copie images + description.json au format attendu par legacy/create_post.py
```

`vto export` assure la continuité : `legacy/create_post.py` continue de créer les brouillons jusqu'au sous-projet 3. Le `description.json` exporté contient les clés lues par `create_post.py` (`title`, `description`, …).

## 6. Migration depuis le prototype

### 6.1 Secrets

- Action de l'utilisateur, hors code : révoquer/régénérer la clé Gemini et changer le mot de passe Vinted.
- `legacy/create_post.py` lit `VINTED_EMAIL` / `VINTED_PASSWORD` depuis l'environnement (seule modification apportée à ce fichier, avec le chemin `ANNONCES_ROOT` lu depuis `VTO_LEGACY_OUTPUT` ou un argument).
- Réécriture de l'historique git (`git filter-repo` + push forcé) : non faite par défaut ; confirmation explicite de l'utilisateur requise au moment voulu. Indispensable seulement si le dépôt devient public ou partagé.

### 6.2 Script `vto.tools.import_legacy`

```
python -m vto.tools.import_legacy <dossier_batch> [--as-default-pack]
```

- `input/backgrounds/<type>/1/*` → `scenes/mannequin/backgrounds/<type>/`
- `input/backgrounds/<type>/2/*` → `scenes/cintre/backgrounds/<type>/`
- `input/clothes/<type>_<nom>/` → nouvel article : photos copiées (`base.*` en premier), `.txt` → `notes`, `garment_type` déduit du préfixe (mappé vers `GarmentType`, `autre` si inconnu).
- Le rappel de promo du prototype est écrit dans `settings.signature`.
- `--as-default-pack` : écrit les scènes dans `default_scenes/` du dépôt au lieu des données utilisateur.
- Le dossier source n'est jamais modifié ni supprimé.

### 6.3 Fichiers du prototype

- `create_post.py` → `legacy/create_post.py` (modifs du 6.1 uniquement).
- `main.py`, `utils.py`, `image_generation.py`, `description.py`, `folder_managment.py` : supprimés une fois le cœur fonctionnel et le test live passé.

## 7. Tests

- **pytest**, `VTO_DATA_DIR` pointé vers un `tmp_path` par test.
- **`FakeClient`** implémentant `GenAIClient` : réponses scriptées (image, JSON, exceptions) ; aucun appel réseau dans la suite par défaut.
- Couverture minimale :
  - `scenes` : sous-dossier par type puis repli ; scène désactivée ignorée ; scène sans décor ignorée ; `render_prompt` ; `ensure_default_scenes` n'écrase rien.
  - `storage` : aller-retour `Article` ; écriture atomique ; transitions autorisées/refusées.
  - `listing` : priorité des champs client ; signature ajoutée ; sortie invalide → `InvalidModelOutput`.
  - `client` (retry) : `TransientError` retentée puis succès ; `InvalidApiKey` sans retry ; 3 échecs → exception.
  - `pipeline` : une scène en échec n'empêche pas les autres ; aucune image → `ERROR` ; annulation → statut correct ; `InvalidApiKey` arrête le lot.
  - `import_legacy` : arborescence factice → scènes + articles attendus, source intacte.
- **Test live** (`@pytest.mark.live`, exclu par défaut) : un vrai vêtement, une scène, l'annonce ; nécessite `GEMINI_API_KEY`.
- **CI** GitHub Actions : Python 3.12, Windows et Ubuntu, `ruff check` + `pytest` (sans `live`).

## 8. Dépendances

`google-genai`, `pydantic`, `Pillow`, `pillow-avif-plugin` (si nécessaire), `platformdirs`, `typer` (CLI). Dev : `pytest`, `ruff`. Python ≥ 3.12.

`selenium` reste une dépendance de `legacy/` uniquement (extra `legacy`) ; `webdriver-manager` est retiré (Selenium Manager suffit).

## 9. Critères d'acceptation

1. `grep` sur le dépôt : aucune clé API, aucun mot de passe, aucun chemin `C:\Users\…`.
2. `pip install -e backend[dev]` puis `pytest` et `ruff check` passent localement et en CI.
3. Le test live passe avec une vraie clé.
4. `import_legacy` sur le dossier `batch` réel, puis `vto run`, produit pour chaque article les images des deux scènes et une annonce valide.
5. `vto export` + `legacy/create_post.py` créent un brouillon Vinted comme avant.
6. Une clé invalide produit le message clair du 4.9 et aucun article n'est perdu.
