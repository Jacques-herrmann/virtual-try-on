# Plan d'implémentation — Sous-projet 1 : Cœur propre

Spec : `docs/superpowers/specs/2026-10-10-core-clean-design.md` (référencée ci-dessous par « spec §x »).
Branche : `feat/core-clean` (créée depuis `spec/core-clean`).

## Conventions

- **TDD** pour chaque module du cœur : écrire le test → le voir échouer → implémenter → `pytest` + `ruff check` verts → commit.
- **Un commit par tâche** (ou sous-étape notable), message court en anglais à l'impératif minuscule, comme l'historique existant (`add scene loading`, `port image utils`).
- Tous les tests utilisent la fixture `data_dir` (`VTO_DATA_DIR` → `tmp_path`). Aucun appel réseau hors `-m live`.
- Ne jamais toucher aux fichiers du prototype avant la tâche 15.
- Cocher les cases au fur et à mesure.

---

## Tâche 0 — Squelette du package et outillage

- [x] `backend/pyproject.toml` : projet `vto`, Python ≥ 3.12, layout `src/`, dépendances (spec §8), extras `dev` (`pytest`, `ruff`) et `legacy` (`selenium`), script `vto = "vto.cli:app"`.
- [x] Config `ruff` (line-length 100, règles `E,F,I,UP,B`) et `pytest` (`testpaths`, marqueur `live` exclu par défaut via `addopts = "-m 'not live'"`).
- [x] `backend/src/vto/__init__.py` (`__version__ = "0.1.0"`), `backend/src/vto/core/__init__.py`, `backend/src/vto/core/generation/__init__.py`.
- [x] `backend/tests/conftest.py` : fixture `data_dir` (monkeypatch `VTO_DATA_DIR`), fixture `make_image(path, size, color)` qui écrit une image PIL.
- [x] `backend/tests/test_smoke.py` : `import vto`.
- [x] `.github/workflows/ci.yml` : matrice `windows-latest` / `ubuntu-latest`, Python 3.12, `pip install -e backend[dev]`, `ruff check backend`, `pytest backend/tests`.
- [x] `.gitignore` : ajouter `*.egg-info/`, `.pytest_cache/`, `.ruff_cache/`.
- [x] Vérifier : `pip install -e backend[dev]` dans `.venv`, `pytest` vert, `ruff check` vert.
- [x] Commit `scaffold vto package with tests and ci`.

## Tâche 1 — `errors.py` et `paths.py` (spec §4.1, §4.9)

- [x] `errors.py` : classe de base `VtoError(Exception)` avec attribut `user_message: str` ; sous-classes `InvalidApiKey`, `QuotaExceeded`, `ModelUnavailable`, `TransientError`, `NoImageReturned`, `InvalidModelOutput`, `NoBackground(scene_name, garment_type)`, `InvalidTransition(from_, to)`, `ArticleNotFound(id)`, `MissingApiKey`. Messages français de la spec §4.9.
- [x] Tests `paths` : `VTO_DATA_DIR` respecté ; sans variable → `platformdirs.user_data_dir("VirtualTryOn", appauthor=False)` ; fonctions `data_dir`, `settings_file`, `scenes_dir`, `articles_dir`, `article_dir(id)`, `logs_dir` ; les dossiers sont créés à la demande.
- [x] Implémenter `paths.py`.
- [x] Commit `add core errors and paths`.

## Tâche 2 — `models.py` (spec §4.3)

- [x] Vérifier sur vinted.fr les libellés actuels des états d'article et des tailles de colis ; ajuster les `Literal` si besoin et noter la date de vérification en commentaire.
- [x] Tests : aller-retour JSON d'un `Article` complet (`model_dump_json` / `model_validate_json`) ; `UserInput` n'exige que `garment_type` ; `Listing` refuse un `condition` hors liste ; `ArticleStatus` sérialisé en chaîne.
- [x] Implémenter `GarmentType`, `ArticleStatus`, `UserInput`, `Listing`, `SceneResult`, `Article`.
- [x] Commit `add core data models`.

## Tâche 3 — `config.py` (spec §4.2)

- [x] Vérifier dans la doc Google AI les noms actuels des modèles image et texte recommandés ; les mettre en défauts.
- [x] Copier le prompt de `description.py` dans `backend/src/vto/core/prompts/listing_default.md` en retirant le rappel de promo et en remplaçant les consignes `[x]` par « utilise null si tu ne sais pas » ; le JSON attendu n'est plus décrit dans le prompt (sortie structurée).
- [x] Tests : `load_settings()` sans fichier → défauts ; `save_settings` puis `load_settings` → identique ; `GEMINI_API_KEY` dans l'env prioritaire sur le fichier ; fichier corrompu → défauts + avertissement loggé (pas de crash) ; `listing_prompt` par défaut = contenu du fichier `.md`.
- [x] Implémenter (`importlib.resources` pour lire le prompt packagé ; déclarer `prompts/*.md` en package data).
- [x] Commit `add settings`.

## Tâche 4 — `storage.py` (spec §4.4)

- [x] Tests :
  - `create_article` copie les photos dans `photos/` (noms `001.jpg`, `002.png`… pour garder l'ordre), écrit `article.json`, statut `DRAFT` ;
  - `load` / `save` aller-retour ; `load` d'un id inconnu → `ArticleNotFound` ;
  - écriture atomique : `save` passe par un fichier temporaire + `os.replace` (vérifier qu'aucun `.tmp` ne traîne et que l'ancien fichier reste intact si la sérialisation échoue) ;
  - `list_articles` trié par `created_at`, ignore un dossier sans `article.json` ;
  - `set_status` : toutes les transitions autorisées de la spec passent, une transition interdite (ex. `DRAFT → PUBLISHED`) lève `InvalidTransition` ;
  - `delete` supprime le dossier (appel explicite uniquement).
- [x] Implémenter (ids `uuid4().hex`).
- [x] Commit `add article storage`.

## Tâche 5 — `images.py` (spec §4.5)

- [x] Vérifier si la version de Pillow installée lit l'AVIF nativement ; sinon ajouter `pillow-avif-plugin` et l'importer dans `images.py`.
- [x] Tests : `load_image` applique l'orientation EXIF (image avec tag Orientation=6 → largeur/hauteur échangées) et renvoie du RGB depuis un PNG RGBA ; `resize_max` ne touche pas une petite image et ramène une 4000×3000 à 1536×1152 ; `is_supported_image` accepte `.JPG`, `.webp`, `.avif`, refuse `.txt` ; `save_jpeg` écrit un JPEG lisible.
- [x] Porter le code utile de `utils.py` (`load_image_as_pil`, `resize_if_needed`, `prepare_for_gemini` — le ré-encodage WEBP est conservé seulement s'il reste utile à l'API, sinon supprimé).
- [x] Commit `port image utils`.

## Tâche 6 — `scenes.py` (spec §4.6)

- [x] Tests :
  - `list_scenes` lit `meta.json` + `prompt.md`, trie par `order`, exclut `enabled: false` (sauf `enabled_only=False`), ignore et logge une scène sans `prompt.md` ou sans aucune image ;
  - `pick_background` : sous-dossier du type présent → tire dedans ; absent ou vide → racine ; rien → `NoBackground` ; déterministe avec un `random.Random(seed)` ;
  - `render_prompt` remplace `{garment_type}` et laisse le reste intact (y compris d'autres accolades) ;
  - `ensure_default_scenes(source)` copie si `scenes/` vide, ne fait rien sinon.
- [x] Implémenter. `default_scenes` est localisé via un paramètre (le packaging du sous-projet 4 décidera de son emplacement final) ; par défaut `<racine du dépôt>/default_scenes`.
- [x] Commit `add scene loading`.

## Tâche 7 — `generation/client.py` (spec §4.7)

- [ ] Lire la doc actuelle du SDK `google-genai` : appel `generate_content` avec images PIL, paramètre de ratio d'image (`ImageConfig(aspect_ratio="3:4")` ou équivalent), sortie structurée (`response_mime_type` + `response_schema`), types d'exceptions (`google.genai.errors.ClientError` / `ServerError`, codes 400/401/403/404/429/5xx) et distinction quota épuisé vs limite de débit.
- [ ] `backend/tests/fakes.py` : `FakeClient(GenAIClient)` avec files de réponses scriptées (`bytes`, objets pydantic ou exceptions) et journal des appels (modèle, prompt, nb d'images).
- [ ] Tests du helper `with_retry(fn, *, attempts=3, base_delay=2, sleep=…)` (sleep injectable pour ne pas attendre) : `TransientError` puis succès → 2 appels ; `NoImageReturned` retentée ; `InvalidApiKey` → 1 seul appel ; 3 échecs → dernière exception relevée ; délais 2/4/8 s ± jitter.
- [ ] Tests de `map_sdk_error(exc) -> VtoError` avec des exceptions SDK construites à la main (401/403 → `InvalidApiKey`, 429 quota → `QuotaExceeded`, 429 débit → `TransientError`, 404 modèle → `ModelUnavailable`, 5xx/timeout → `TransientError`).
- [ ] Implémenter `GenAIClient` (Protocol), `with_retry`, `map_sdk_error`, `GeminiClient` (images converties via `images.py`, réponse image extraite des `inline_data`, aucune image → `NoImageReturned`, JSON validé par le schéma sinon `InvalidModelOutput`).
- [ ] Commit `add gemini client with retries and error mapping`.

## Tâche 8 — `generation/image.py` (spec §4.7)

- [ ] Tests (FakeClient, scène et article créés dans `data_dir`) : le client reçoit `[prompt rendu, décor, vêtement]` dans cet ordre avec `settings.image_model` ; l'image est écrite dans `generated/<slug>.jpg` ; `NoBackground` propagée ; la photo du vêtement utilisée est la première de l'article.
- [ ] Implémenter `generate_scene_image`.
- [ ] Commit `add scene image generation`.

## Tâche 9 — `generation/listing.py` (spec §4.7)

- [ ] Tests : le prompt envoyé contient `settings.listing_prompt` + bloc « Informations connues » avec uniquement les champs non nuls et les notes ; images envoyées = première image générée OK + photo d'origine (photo d'origine seule si aucune image générée) ; champs `UserInput` renseignés écrasent `Listing` ; signature ajoutée après une ligne vide, rien si vide ; `InvalidModelOutput` propagée.
- [ ] Implémenter `generate_listing`.
- [ ] Commit `add listing generation`.

## Tâche 10 — `pipeline.py` (spec §4.8)

- [ ] Tests (FakeClient) :
  - nominal 2 scènes → 2 `SceneResult` ok, `listing` rempli, statut `TO_REVIEW`, article sauvé après chaque scène (vérifier via `on_progress` ou relecture disque) ;
  - une scène en `NoImageReturned` persistant → l'autre ok, statut `TO_REVIEW`, erreur lisible dans le `SceneResult` ;
  - toutes les scènes en échec → `ERROR` ;
  - annonce en `InvalidModelOutput` → `ERROR` ;
  - `InvalidApiKey` → article `ERROR`, exception propagée, `process_batch` s'arrête (le 2ᵉ article reste `DRAFT`) ;
  - annulation avant la 1ʳᵉ scène → `DRAFT` ; après une scène réussie → `TO_REVIEW` ;
  - régénération d'une seule scène sur un article `TO_REVIEW` : seule cette scène est rappelée, l'annonce n'est pas régénérée ;
  - `regenerate_listing` ne touche pas aux images ;
  - `MissingApiKey` si aucune clé configurée (vérifiée avant de passer en `GENERATING`).
- [ ] Implémenter `process_article`, `process_batch`, `regenerate_listing` ; `build_client(settings)` construit un `GeminiClient` (le seul endroit qui l'instancie).
- [ ] Commit `add article pipeline`.

## Tâche 11 — Logging

- [ ] `core/logging.py` : `setup_logging()` → `RotatingFileHandler` dans `logs_dir()/vto.log` (1 Mo × 3), niveau INFO, + console optionnelle.
- [ ] Test : un message loggé apparaît dans le fichier.
- [ ] Commit `add file logging`.

## Tâche 12 — CLI `vto` (spec §5)

- [ ] Tests avec `typer.testing.CliRunner` et `FakeClient` injecté (fonction `get_client` surchargeable dans le module CLI) : `config set-key` écrit la clé ; `add` crée un article avec les bons champs ; `list` affiche id/statut/type/titre ; `run` traite les `DRAFT` ; `regen --scene` ; `show` ; une `VtoError` affiche `user_message` et code de sortie 1, sans trace.
- [ ] Test `export` : produit `0.jpg`, `1.jpg`… (images générées dans l'ordre des scènes puis photos d'origine) et un `description.json` lisible par `VintedDraftCreator._load_item_data` du prototype (clés `title`, `description`, `category`, `brand`, `size`, `condition`, `color`, `price`, `parcel_size`).
- [ ] Implémenter `cli.py` (le CLI appelle `setup_logging()` et `ensure_default_scenes()` au démarrage).
- [ ] Commit `add dev cli`.

## Tâche 13 — Pack de scènes par défaut et import du prototype (spec §4.6, §6.2)

- [ ] `default_scenes/mannequin/` et `default_scenes/cintre/` : `meta.json` + `prompt.md` (= `PROMPT_DUMMY` / `PROMPT_HANGER` ; retirer la consigne de ratio en majuscules si la tâche 7 a confirmé le paramètre API ; remplacer les mentions génériques du type par `{garment_type}` uniquement si ça n'altère pas le sens).
- [ ] Tests `import_legacy` sur une arborescence factice : scènes créées avec sous-dossiers par type ; articles créés avec `base.*` en première photo, `.txt` → `notes`, préfixe → `GarmentType` (table de correspondance, `autre` par défaut) ; signature écrite ; source intacte (hash des fichiers avant/après) ; `--as-default-pack` écrit dans le dossier cible fourni.
- [ ] Implémenter `vto.tools.import_legacy` (argparse).
- [ ] **Avec l'utilisateur** : lister les préfixes de type réellement utilisés dans `Twake\Annonces\batch\input\clothes` pour compléter la table de correspondance ; lancer `--as-default-pack` sur le vrai dossier ; décider si les images du pack sont versionnées telles quelles ou compressées (taille du dépôt).
- [ ] Commit `add default scenes and legacy import`.

## Tâche 14 — `legacy/create_post.py` (spec §6.1)

- [ ] `git mv create_post.py legacy/create_post.py`.
- [ ] Remplacer `EMAIL`/`PASSWORD` par `os.environ["VINTED_EMAIL"]` / `os.environ["VINTED_PASSWORD"]` (message clair si absents) et `ANNONCES_ROOT` par `VTO_LEGACY_OUTPUT` ou `sys.argv[1]`. Supprimer `webdriver-manager` (`webdriver.Chrome(options=options)` utilise Selenium Manager). Aucune autre modification.
- [ ] `legacy/README.md` : 5 lignes sur l'usage transitoire (`vto export` puis `create_post.py`).
- [ ] Commit `move vinted draft script to legacy and read credentials from env`.

## Tâche 15 — Test live, nettoyage et acceptation (spec §7, §9)

- [ ] `backend/tests/test_live.py` (`@pytest.mark.live`) : image de vêtement de test versionnée (petite, libre de droits), scène `mannequin`, `process_article` réel → image non vide + `Listing` valide. Ignoré si `GEMINI_API_KEY` absente.
- [ ] **Avec l'utilisateur** (nouvelle clé) : `pytest -m live` vert.
- [ ] Supprimer `main.py`, `utils.py`, `image_generation.py`, `description.py`, `folder_managment.py`.
- [ ] Vérifier les critères d'acceptation spec §9 :
  1. `git grep -nE "AIza|PASSWORD *=|C:\\\\Users"` → rien dans l'arbre courant ;
  2. install propre + `pytest` + `ruff` verts, CI verte ;
  3. test live vert ;
  4. `import_legacy` + `vto run` sur le vrai dossier (avec l'utilisateur) ;
  5. `vto export` + `legacy/create_post.py` → brouillon créé (avec l'utilisateur) ;
  6. clé invalide → message clair, articles intacts.
- [ ] Mettre à jour `CLAUDE.md` (statut sous-projet 1 ✅, section « État du dépôt »).
- [ ] Commit `remove prototype scripts`, puis PR `feat/core-clean` → `main`.

---

## Points nécessitant l'utilisateur

| Tâche | Besoin |
|---|---|
| avant 15 | Nouvelle clé Gemini (l'ancienne est révoquée) |
| 13 | Accès au dossier `Twake\Annonces\batch`, validation de la table type → `GarmentType`, choix sur le poids du pack |
| 15 | Test live, essai bout en bout avec Vinted |
| hors plan | Réécriture de l'historique git (confirmation explicite requise) |
