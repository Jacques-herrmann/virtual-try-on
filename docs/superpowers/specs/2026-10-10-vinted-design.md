# Sous-projet 3 — Vinted — Design

Date : 2026-10-10
Statut : validé en brainstorming, en attente de relecture

## 1. Contexte

Le sous-projet 2 a livré l'app (API FastAPI + UI Vue) jusqu'à la validation d'un article. L'envoi sur Vinted repose encore sur `legacy/create_post.py` : Selenium, connexion par e-mail et mot de passe stockés dans `.env`, sélecteurs en dur, seuls le titre, la description et les photos sont remplis. Ce sous-projet remplace ce script par un package `vto.vinted` piloté depuis l'app.

### 1.1 Décisions (prises en brainstorming)

| Sujet | Décision |
|---|---|
| Action finale | Brouillon par défaut ; réglage pour publier directement |
| Champ non rempli | Le robot continue, enregistre **toujours en brouillon** (même en mode publier) et marque l'article « À compléter sur Vinted » avec la liste des champs manquants ; passe à l'article suivant |
| Catégorie | Arbre des catégories Vinted livré comme données ; Gemini choisit une catégorie valide ; le vendeur la corrige à la relecture ; le robot clique chaque niveau du chemin |
| Tailles, couleurs | Même principe : grilles de tailles par catégorie et liste de couleurs dans les données |
| Données distantes | Un fichier `vinted.json` brut sur GitHub, mis en cache, avec copie embarquée en repli. L'URL sera remplacée par le Worker du sous-projet 5 |
| Navigateur | Playwright (Python), Chrome installé sinon Edge, profil dédié persistant. Connexion manuelle une fois par le vendeur ; aucun mot de passe stocké |
| Ordre des photos | Inclus : galerie réordonnable à la relecture, inclusion optionnelle des photos d'origine |

Approches écartées : Selenium (Selenium Manager télécharge chromedriver chez le client, attentes manuelles) ; connexion CDP au Chrome habituel du vendeur (bloquée sur le profil par défaut depuis Chrome 136, oblige à relancer son navigateur) ; suggestion de catégorie de Vinted (non vérifiable à la relecture) ; catégorie en texte libre (erreurs silencieuses).

### 1.2 Hors périmètre

- Modifier, republier ou supprimer une annonce existante sur Vinted.
- Plusieurs comptes Vinted.
- Autres pays que vinted.fr.
- Mode headless.
- Signature du fichier de données (TLS suffit tant que le fichier ne contient que des données).

## 2. Architecture

### 2.1 Arborescence

```
backend/src/vto/
  core/                 complété (§3)
  vinted/
    schema.py           modèles pydantic de vinted.json (§4)
    remote.py           load_vinted_data() : téléchargement, validation, cache, copie embarquée
    catalog.py          Catalog : chemins, feuilles par type/public, grilles de tailles
    browser.py          open_context() : contexte persistant Chrome → Edge ; is_logged_in()
    locators.py         traduction d'un localisateur (données) en Locator Playwright
    filler.py           fill_item(page, article, data, mode) → FillReport
    worker.py           VintedWorker : thread unique, connexion, lots, arrêt, pause
    data/vinted.json    copie embarquée
  api/routes/vinted.py  routes /vinted/* (§6)
  tools/vinted_catalog.py   outil de dev (§8)
data/vinted.json        fichier publié (servi par raw.githubusercontent.com)
```

`vto.core` n'importe jamais `vto.vinted`. `vto.vinted` dépend de `core` ; `api` dépend des deux.

### 2.2 Dépendances

- Ajout : `playwright` (dépendance principale ; le driver est inclus dans le paquet pip, aucun navigateur téléchargé chez le client puisqu'on utilise `channel="chrome"` puis `channel="msedge"`), `httpx` (téléchargement des données).
- Suppression : extra `legacy` (`selenium`).

## 3. Changements dans le cœur

### 3.1 `models.py`

- `Listing.category: str | None` contient désormais un **identifiant de catégorie Vinted** (entier sérialisé en chaîne, ex. `"1779"`).
- `Listing.color: list[str]` (0 à 2 couleurs prises dans la liste Vinted) au lieu de `str | None`.
- `UserInput.color` reste un texte libre (indication donnée à Gemini).
- Nouveau `VintedResult` :
  ```python
  class VintedResult(BaseModel):
      mode: Literal["draft", "publish"]          # action réellement effectuée
      status: Literal["ok", "partial", "error"]
      missing_fields: list[str] = []             # libellés français : « Marque », « Taille »…
      url: str | None = None
      error: str | None = None                   # message client, en français
      sent_at: datetime
  ```
- `Article.vinted: VintedResult | None = None`.
- `Article.gallery: list[str] | None = None` : chemins (relatifs au dossier de l'article) des images à envoyer, dans l'ordre. `None` = ordre par défaut : images des scènes `ok` non exclues, dans l'ordre des scènes ; aucune photo d'origine. Maximum 20.
- Statut : un envoi `ok` ou `partial` fait passer l'article en `PUBLISHED` (qu'il s'agisse d'un brouillon ou d'une publication ; le détail est dans `vinted`). Un envoi `error` le laisse en `VALIDATED`.

### 3.2 Migration au chargement (`storage.py`)

Validateurs `mode="before"` sur `Listing` : une `category` non numérique devient `None` ; une `color` texte devient `[color]` si elle est non vide, sinon `[]`. Le cœur ne connaît pas la liste Vinted : une couleur inconnue est signalée à la relecture (l'UI ne la propose pas) et à l'envoi (champ manquant). Rien d'autre n'est modifié ni supprimé.

### 3.3 Génération de l'annonce (`generation/listing.py`)

`generate_listing(client, settings, article, choices)` reçoit un `ListingChoices` (défini dans `core.models`) :

```python
class ListingChoices(BaseModel):
    categories: dict[str, str]   # id → chemin lisible, déjà filtrés par type/public
    colors: list[str]
```

Le schéma de sortie passé à Gemini est construit dynamiquement : `category` est une énumération des ids fournis, `color` une liste d'énumérations de `colors` (max 2). Le prompt liste les chemins lisibles. Le pipeline reçoit un fournisseur `choices_for(article) -> ListingChoices` injecté par l'appelant (l'API le construit à partir du `Catalog`). Sans fournisseur (CLI de dev, tests du cœur), les champs restent libres comme aujourd'hui.

La taille reste choisie par Gemini en texte ; elle est confrontée à la grille de la catégorie à la relecture (l'UI propose la grille) et à l'envoi.

### 3.4 `config.py`

`Settings.vinted_mode: Literal["draft", "publish"] = "draft"`.

### 3.5 `paths.py`

`browser_profile_dir()` → `<data>/browser-profile`, `cache_dir()` → `<data>/cache`, `vinted_log_dir()` → `<data>/logs/vinted`.

## 4. Fichier `vinted.json`

### 4.1 Format

```jsonc
{
  "format": 1,
  "revision": "2026-10-10.1",
  "urls": { "home": "https://www.vinted.fr", "new_item": "https://www.vinted.fr/items/new" },
  "locators": {
    "logged_in":       [{ "css": "[data-testid='header--avatar']" }],
    "cookie_accept":   [{ "css": "#onetrust-accept-btn-handler" }],
    "popup_close":     [{ "css": "[data-testid='modal-close-button']" }],
    "photo_input":     [{ "css": "input[type='file']" }],
    "photo_thumb":     [{ "css": "[data-testid^='photo-thumbnail']" }],
    "title":           [{ "css": "[data-testid='title--input']" }, { "label": "Titre" }],
    "description":     [{ "css": "[data-testid='description--input']" }],
    "category_open":   [{ "css": "[data-testid='catalog-select-dropdown-input']" }],
    "category_option": [{ "role": "button", "name": "{label}" }],
    "brand_open":      [ ... ], "brand_input": [ ... ], "brand_option": [ ... ],
    "size_open":       [ ... ], "size_option": [ ... ],
    "condition_open":  [ ... ], "condition_option": [ ... ],
    "color_open":      [ ... ], "color_option": [ ... ], "color_close": [ ... ],
    "price":           [ ... ],
    "parcel_option":   [ ... ],
    "save_draft":      [{ "role": "button", "name": "Enregistrer le brouillon" }],
    "publish":         [{ "role": "button", "name": "Ajouter" }],
    "saved_marker":    [ ... ]
  },
  "catalog": [
    { "id": 1904, "label": "Femmes", "children": [
      { "id": 4, "label": "Vêtements", "children": [
        { "id": 1779, "label": "Robes mi-longues", "size_group": "4", "garment_types": ["robe"] }
      ]}
    ]}
  ],
  "size_groups": { "4": ["XS", "S", "M", "L", "XL", "XXL"] },
  "conditions": { "Neuf": "Neuf avec étiquette", "Comme neuf": "Neuf sans étiquette",
                  "Très bon état": "Très bon état", "Bon état": "Bon état", "Satisfaisant": "Satisfaisant" },
  "colors": ["Noir", "Blanc", "Gris", "Beige", "..."],
  "parcel_sizes": { "Petit": "Petit", "Moyen": "Moyen", "Grand": "Grand" },
  "audiences": { "femme": 1904, "homme": 5, "enfant": 1193 }
}
```

Les valeurs ci-dessus sont illustratives ; les vraies sont relevées sur vinted.fr pendant l'implémentation.

- **Localisateur** : liste d'alternatives essayées dans l'ordre jusqu'à ce qu'une soit visible. Chaque alternative a exactement une des formes `{"css"}`, `{"label"}`, `{"text"}`, `{"role", "name"}`. Seul `{label}` est substitué dans `name`, `text` et `label`, par une valeur échappée ; aucune autre interprétation.
- **Catalogue** : `size_group` (optionnel) sur les feuilles, absent = pas de taille. `garment_types` (optionnel) sur n'importe quel nœud, hérité par les descendants, sert à filtrer les feuilles proposées à Gemini ; une feuille sans `garment_types` hérité n'est proposée que pour `autre`. `audiences` donne la racine à utiliser selon le public ; public inconnu = toutes les racines.

### 4.2 Validation (`schema.py`)

Modèles pydantic `extra="forbid"`. Rejet si : `format != 1` ; ids de catégorie non uniques ; `size_group` inexistant ; clé de `conditions` hors des `Condition` du cœur ; clé de `parcel_sizes` hors des `ParcelSize` ; localisateur requis absent ou liste vide ; alternative avec zéro ou plusieurs formes.

### 4.3 Chargement (`remote.py`)

`load_vinted_data() -> LoadedData(data, source: "remote" | "cache" | "bundled", revision)` :

1. GET sur l'URL (défaut `https://raw.githubusercontent.com/Jacques-herrmann/virtual-try-on/main/data/vinted.json`, surchargeable par `VTO_VINTED_DATA_URL`), délai 5 s, `If-None-Match` avec l'ETag du cache.
2. 200 et valide → écrit `<cache>/vinted.json` et `<cache>/vinted.etag` (écriture atomique), source `remote`. 304 → cache. Invalide, erreur réseau ou HTTP → cache s'il est valide, sinon copie embarquée.
3. Le log indique toujours la source, la révision et la raison d'un repli.

Appelé au démarrage de l'app et au début de chaque lot. La copie embarquée et `data/vinted.json` sont identiques (test).

## 5. Navigateur et remplissage

### 5.1 `browser.py`

`open_context()` : `playwright.chromium.launch_persistent_context(browser_profile_dir(), channel="chrome", headless=False, locale="fr-FR", viewport=None, args=["--start-maximized"])`, puis `channel="msedge"` si Chrome est absent. Erreurs traduites : aucun navigateur → `BrowserMissing` ; profil verrouillé → `ProfileInUse`.

`is_logged_in(page, data)` : `goto(home)` si nécessaire, puis visibilité de `logged_in` (3 s).

### 5.2 `filler.py`

`fill_item(page, article, data, catalog, mode) -> FillReport(status, missing_fields, url, error)`. Étapes, chacune isolée (une exception est capturée, journalisée avec le nom du localisateur, une capture d'écran est enregistrée dans `vinted_log_dir()`, et le libellé du champ est ajouté à `missing_fields`) :

1. `goto(new_item)` ; cookies ; pop-ups. Échec de chargement → `error` immédiat (« Vinted ne répond pas »).
2. Photos : `set_input_files` avec la galerie dans l'ordre ; attente de N miniatures `photo_thumb` (30 s). Échec → `error` (une annonce sans photo ne peut pas être enregistrée).
3. Titre, description : `fill`.
4. Catégorie : `category_open`, puis clic sur chaque libellé du chemin (`category_option`). Catégorie absente ou inconnue du catalogue → manquant.
5. Marque : `brand_open`, saisie dans `brand_input`, clic sur la suggestion dont le libellé est égal à la marque (casse et accents ignorés). Aucune → manquant.
6. Taille : si la catégorie a une grille et que la taille y figure → `size_open` + `size_option` ; si la catégorie n'a pas de grille → étape sautée ; sinon manquant.
7. État : libellé traduit par `conditions`.
8. Couleurs : chaque couleur via `color_option`, puis `color_close`. Couleur inconnue → manquant.
9. Prix : `fill` au format `12,50`. Absent → manquant.
10. Colis : libellé traduit par `parcel_sizes` ; absent → étape sautée (Vinted propose une valeur par défaut).
11. Enregistrement : `publish` si `mode == "publish"` et aucun champ manquant, sinon `save_draft`. Attente de `saved_marker` ou d'un changement d'URL (20 s). Échec → `error` (« L'annonce n'a pas pu être enregistrée sur Vinted »).

Résultat : `ok` si aucun champ manquant, `partial` sinon ; `mode` réellement effectué ; `url` = `page.url` après enregistrement.

Libellés des champs manquants : Catégorie, Marque, Taille, État, Couleur, Prix (titre et description vides comptent aussi : Titre, Description).

### 5.3 `worker.py`

`VintedWorker` possède un thread et l'unique contexte Playwright (API synchrone, utilisée uniquement dans ce thread). Commandes reçues par une file :

- `connect()` : ouvre le contexte sur `home`, vérifie `logged_in` toutes les 2 s pendant 10 min, puis ferme. État `connected` mis à jour.
- `disconnect()` : ferme le contexte s'il est ouvert, supprime `browser_profile_dir()` (seul effacement fait par ce sous-projet ; ce n'est pas une donnée client ; confirmation dans l'UI).
- `send(article_ids)` : refusé si un lot tourne déjà. Charge les données (§4.3), ouvre le contexte, vérifie la connexion ; si déconnecté → pause `login_required` et attente de `logged_in` (10 min, sinon fin du lot). Pour chaque article encore `validated` : `fill_item`, enregistrement du `VintedResult`, mise à jour du statut, pause aléatoire 4 à 10 s. Ferme le contexte à la fin.
- `stop()` : termine l'article en cours, puis arrête le lot.
- `open_url(url)` : ouvre l'URL dans le contexte dédié (déjà connecté) et laisse la fenêtre au vendeur.

Fenêtre fermée par le vendeur pendant un lot (contexte ou page fermés) → fin du lot ; l'article en cours reçoit `error`, les suivants restent `validated` sans `vinted`.

État exposé : `connected: bool | None` (inconnu avant la première vérification), `batch: {running, paused_reason: "login_required" | None, current: article_id | None, done, total, failed}`.

## 6. API

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/vinted/status` | `{connected, data_revision, data_source, batch}` |
| POST | `/vinted/connect` | lance la connexion (202) |
| POST | `/vinted/disconnect` | ferme et efface le profil navigateur |
| POST | `/vinted/send` | `{article_ids}` ; 409 si un lot tourne ; 422 si un article n'est pas `validated` |
| POST | `/vinted/stop` | arrête le lot après l'article en cours |
| POST | `/vinted/open` | `{article_id}` ; ouvre `vinted.url` dans la fenêtre dédiée |
| GET | `/vinted/catalog` | arbre, grilles de tailles, couleurs, états, colis |
| PATCH | `/articles/{id}/gallery` | `{gallery: list[str] | null}` ; chemins appartenant à l'article (images de scènes `ok` ou photos d'origine), sans doublon, 1 à 20 |

`PATCH /articles/{id}/listing` accepte `category` (id présent dans le catalogue, sinon 422) et `color: list[str]` (max 2). `GET /settings` / `PATCH /settings` exposent `vinted_mode`. Les erreurs suivent le format et les codes du §4.4 de la spec de l'app.

## 7. UI

- **Relecture** : bandeau de la galerie réordonnable par glisser-déposer ; photos d'origine affichées à la suite avec une case « Inclure » ; compteur « n / 20 ». Catégorie via `CascadeSelect` de PrimeVue (chemin complet affiché) ; taille via la grille de la catégorie (champ masqué si la catégorie n'a pas de grille ; une taille hors grille est signalée) ; couleurs en multi-sélection (max 2) ; état et colis en listes.
- **Liste des articles** : sélection multiple des articles validés → bouton « Envoyer sur Vinted (n) ». Panneau de lot : progression, article en cours, « Arrêter », message de pause « Connectez-vous dans la fenêtre Vinted ». Badges : « Brouillon Vinted », « Publié sur Vinted », « À compléter sur Vinted » (champs manquants au survol), « Échec de l'envoi » (message). Action « Ouvrir sur Vinted » (`/vinted/open`) et, pour un échec, « Réessayer ».
- **Réglages › Vinted** : état de connexion ; « Connecter mon compte » / « Déconnecter » (confirmation) ; mode « Enregistrer en brouillon » / « Publier directement » avec la mention « Une annonce incomplète est toujours enregistrée en brouillon » ; révision et source des données Vinted.
- Polling de `/vinted/status` toutes les 2 s pendant un lot ou une connexion, comme pour la file de génération.

## 8. Outil de dev `vto-vinted-catalog`

Script `vto.tools.vinted_catalog` (entrée `vto-vinted-catalog`, hors de l'app livrée au client) : ouvre le profil dédié sur `new_item`, parcourt récursivement le sélecteur de catégories, relève pour chaque feuille la grille de tailles proposée et la liste des couleurs, puis réécrit les sections `catalog`, `size_groups` et `colors` de `data/vinted.json` en conservant `garment_types`, `audiences` et `locators` (maintenus à la main). Incrémente `revision`. On relit le diff avant de commiter, puis on recopie le fichier dans `vto/vinted/data/`.

## 9. Erreurs

| Cas | Message client |
|---|---|
| Ni Chrome ni Edge | « Installez Google Chrome ou Microsoft Edge pour envoyer vos annonces. » |
| Profil verrouillé | « Une fenêtre Vinted de l'application est déjà ouverte. Fermez-la puis réessayez. » |
| Fenêtre fermée pendant un lot | « La fenêtre Vinted a été fermée. n articles n'ont pas été envoyés. » |
| Page non chargée | article en échec : « Vinted ne répond pas. Réessayez plus tard. » ; le lot continue |
| Photos non envoyées | article en échec : « Les photos n'ont pas pu être envoyées sur Vinted. » |
| Enregistrement impossible | article en échec : « L'annonce n'a pas pu être enregistrée sur Vinted. » |
| Connexion non faite en 10 min | « Connexion à Vinted non détectée. Réessayez. » |
| Données Vinted inutilisables | « L'envoi sur Vinted est momentanément indisponible. » |

Détails techniques (localisateur, révision des données, trace, capture d'écran) dans le log uniquement. Aucun identifiant Vinted n'est lu, stocké ni journalisé par l'app.

## 10. Suppression du legacy

Suppression de `legacy/` et de l'extra `legacy`. `VINTED_EMAIL` et `VINTED_PASSWORD` ne sont plus utilisés ; CLAUDE.md et la doc sont mis à jour pour retirer ces variables.

## 11. Tests

Tous sans réseau, sauf marqueurs explicites.

- **schema / remote** : la copie embarquée est valide et identique à `data/vinted.json` ; rejets du §4.2 ; ordre de repli réseau → cache → embarqué et 304 avec ETag (`httpx.MockTransport`).
- **catalog** : chemin d'un id, feuilles filtrées par type et public avec héritage de `garment_types`, grille d'une feuille.
- **locators** : traduction de chaque forme ; échappement de `{label}`.
- **filler** (marqueur `browser`) : page factice `tests/vinted/fixtures/new_item.html` servie localement, pilotée par le Chromium de Playwright avec un `vinted.json` de test pointant sur ses éléments. Cas : remplissage complet → `ok` et brouillon ; mode publier complet → bouton publier ; un champ absent → `partial` + brouillon même en mode publier ; marque introuvable ; catégorie sans grille → taille sautée ; bouton d'enregistrement absent → `error`. Sautés si aucun navigateur n'est disponible ; la CI lance `playwright install chromium`.
- **worker** (`FakeFiller`, faux contexte) : lot complet, arrêt, pause `login_required` puis reprise, fenêtre fermée, statuts et `VintedResult` des articles, lot refusé si un autre tourne.
- **API** : routes `/vinted/*`, validation de `gallery`, de `category` et de `color`.
- **cœur** : schéma dynamique transmis à `FakeClient` (énumérations de catégories et de couleurs) ; comportement inchangé sans fournisseur ; migration des anciens articles ; galerie par défaut.
- **front** (Vitest) : réordonnancement et inclusion dans la galerie, limite de 20, cascade de catégorie, grille de tailles, badges.
- **`pytest -m live_vinted`** (manuel, profil de dev déjà connecté) : crée un brouillon réel ; suppression manuelle ensuite.

## 12. Critères d'acceptation

1. Connexion manuelle une fois ; trois lancements de l'app ensuite sans avoir à se reconnecter.
2. Lot de 5 articles réels en mode brouillon : tous les champs remplis, photos dans l'ordre choisi, brouillons visibles sur Vinted.
3. Mode publier sur 1 article réel : annonce en ligne.
4. Un localisateur volontairement cassé dans le cache : l'article finit en brouillon « À compléter » avec le bon champ signalé.
5. Hors ligne : l'app démarre sur le cache ; le log indique la source.
6. Aucun identifiant Vinted dans le code, les réglages ni les logs.
