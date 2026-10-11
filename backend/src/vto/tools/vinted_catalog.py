"""Relevé du catalogue Vinted (outil de développement, hors de l'app livrée).

    vto-vinted-catalog [--data data/vinted.json] [--limit N] [--restart]

Ouvre le profil du navigateur dédié (vendeur de test connecté) sur « Vends ton article »,
lit l'arbre des catégories, puis choisit chaque catégorie finale pour relever sa grille de
tailles. Tout est capté passivement dans les réponses que la page reçoit : aucun appel
direct à l'API (DataDome). Le relevé est repris là où il s'est arrêté (`--restart` pour
tout refaire).

Réécrit `catalog`, `size_groups` et `colors` du fichier ; `garment_types` (par id),
`audiences`, `locators` et les libellés restent ceux maintenus à la main. Relire le diff,
compléter les `garment_types` des nouvelles branches, puis recopier le fichier dans
`backend/src/vto/vinted/data/`.
"""

import argparse
import json
import logging
import random
import re
import unicodedata
from datetime import date
from pathlib import Path

from vto.core import paths
from vto.core.logging import setup_logging
from vto.vinted import browser
from vto.vinted.schema import VintedData

log = logging.getLogger(__name__)

CATALOGS_API = "/api/v2/item_upload/catalogs"
ATTRIBUTES_API = "/api/v2/item_upload/attributes"
COLORS_API = "/api/v2/item_upload/colors"

STEP_MS = 15_000
PAUSE_MS = (400, 1000)
MAX_BACK = 8


# --- Lecture des réponses de Vinted (sans navigateur) ---------------------------------------


def tree_from_catalogs(body: dict, roots: set[int]) -> list[dict]:
    """Arbre `{id, label, children}` des racines voulues, dans l'ordre de Vinted."""

    def convert(node: dict) -> dict:
        children = [convert(child) for child in node.get("catalogs") or []]
        return {"id": node["id"], "label": node["title"].strip(), "children": children}

    return [convert(node) for node in body["catalogs"] if node["id"] in roots]


def sizes_from_attributes(body: dict) -> list[str] | None:
    """Libellés de la grille de tailles proposée, dans l'ordre ; None sans champ taille."""
    size = next((a for a in body.get("attributes", []) if a.get("code") == "size"), None)
    if not size or not size.get("configuration"):
        return None
    labels: list[str] = []

    def collect(options: list[dict]) -> None:
        for option in options:
            if option.get("options"):
                collect(option["options"])
            elif option.get("type") != "group" and option.get("title"):
                labels.append(option["title"])

    collect(size["configuration"].get("options") or [])
    return list(dict.fromkeys(labels)) or None


def colors_from_response(body: dict) -> list[str]:
    colors = sorted(body["colors"], key=lambda c: c.get("order", 0))
    return [c["title"] for c in colors]


def leaves(tree: list[dict]) -> list[tuple[dict, list[int]]]:
    """Feuilles avec le chemin d'ids depuis la racine, dans l'ordre de l'arbre."""
    found = []

    def walk(node: dict, path: list[int]) -> None:
        path = [*path, node["id"]]
        if not node["children"]:
            found.append((node, path))
        for child in node["children"]:
            walk(child, path)

    for root in tree:
        walk(root, [])
    return found


# --- Fusion (sans navigateur) -----------------------------------------------------------------


def next_revision(revision: str, today: date) -> str:
    """« 2026-10-11.3 » → « 2026-10-11.4 » le même jour, « <aujourd'hui>.1 » sinon."""
    day = today.isoformat()
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.(\d+)", revision)
    if match and match.group(1) == day:
        return f"{day}.{int(match.group(2)) + 1}"
    return f"{day}.1"


def _slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def merge(existing: dict, scraped: dict, today: date) -> dict:
    """Nouveau contenu de `vinted.json`.

    `scraped` : `{"catalog": [...], "sizes": {id: [libellés] | None}, "colors": [...]}`.
    Les `garment_types` sont gardés sur les ids existants ; les nœuds disparus sont retirés ;
    une grille identique à une grille existante en reprend le nom.
    """
    types: dict[int, list[str]] = {}

    def remember(node: dict) -> None:
        if node.get("garment_types") is not None:
            types[node["id"]] = node["garment_types"]
        for child in node.get("children", []):
            remember(child)

    for root in existing["catalog"]:
        remember(root)

    names = {tuple(labels): name for name, labels in existing["size_groups"].items()}
    size_groups: dict[str, list[str]] = {}

    def group_for(labels: list[str], path: list[str]) -> str:
        key = tuple(labels)
        name = names.get(key)
        if name is None:
            base = _slug("-".join(path[:2])) or "grille"
            name, n = base, 2
            while name in size_groups or name in existing["size_groups"]:
                name, n = f"{base}-{n}", n + 1
            names[key] = name
        size_groups[name] = labels
        return name

    def build(node: dict, path: list[str]) -> dict:
        path = [*path, node["label"]]
        out: dict = {"id": node["id"], "label": node["label"]}
        if node["id"] in types:
            out["garment_types"] = types[node["id"]]
        if node["children"]:
            out["children"] = [build(child, path) for child in node["children"]]
        else:
            labels = scraped["sizes"].get(node["id"])
            if labels:
                out["size_group"] = group_for(labels, path)
        return out

    merged = dict(existing)
    merged["revision"] = next_revision(existing["revision"], today)
    merged["catalog"] = [build(root, []) for root in scraped["catalog"]]
    merged["size_groups"] = dict(sorted(size_groups.items()))
    merged["colors"] = scraped["colors"]
    VintedData.model_validate(merged)
    return merged


# --- Relevé dans le navigateur ----------------------------------------------------------------


class _Scraper:
    def __init__(self, page, data: VintedData):
        self.page = page
        self.data = data
        self.colors: dict | None = None  # reçues après le choix d'une première catégorie
        page.on("response", self._on_response)

    def _on_response(self, response) -> None:
        if COLORS_API in response.url and response.ok:
            try:
                self.colors = response.json()
            except Exception:
                log.debug("Réponse des couleurs illisible", exc_info=True)

    def pause(self) -> None:
        self.page.wait_for_timeout(random.uniform(*PAUSE_MS))

    def open_form(self) -> dict:
        """Charge le formulaire ; renvoie l'arbre des catégories reçu par la page."""
        with self.page.expect_response(lambda r: CATALOGS_API in r.url, timeout=60_000) as cat:
            self.page.goto(self.data.urls.new_item, wait_until="domcontentloaded")
        return cat.value.json()

    def _visible(self, category_id: int) -> bool:
        return self.page.locator(f"#catalog-{category_id}").first.is_visible()

    def _click(self, category_id: int) -> None:
        option = self.page.locator(f"#catalog-{category_id}").first
        option.scroll_into_view_if_needed(timeout=STEP_MS)
        option.click(timeout=STEP_MS)
        self.pause()

    def sizes_of(self, path: list[int]) -> list[str] | None:
        """Choisit la feuille au bout de `path` et lit la grille renvoyée par Vinted."""
        leaf = path[-1]
        self.page.locator("[data-testid='catalog-select-dropdown-input']").click(timeout=STEP_MS)
        self.pause()
        # La liste se rouvre d'ordinaire à la racine ; sinon on remonte.
        back = self.page.get_by_role("button", name="Revenir en arrière")
        for _ in range(MAX_BACK):
            if self._visible(path[0]):
                break
            back.first.click(timeout=STEP_MS)
            self.pause()
        for category_id in path[:-1]:
            self._click(category_id)

        def is_leaf_request(response) -> bool:
            if ATTRIBUTES_API not in response.url or response.request.method != "POST":
                return False
            try:
                sent = json.loads(response.request.post_data or "{}")
            except ValueError:
                return False
            return any(
                a.get("code") == "category" and a.get("value") == [leaf]
                for a in sent.get("attributes", [])
            )

        with self.page.expect_response(is_leaf_request, timeout=STEP_MS) as response:
            self._click(leaf)
        return sizes_from_attributes(response.value.json())


def _progress_file() -> Path:
    return paths.cache_dir() / "vinted_catalog_progress.json"


def scrape(page, data: VintedData, progress: dict, limit: int | None) -> dict:
    scraper = _Scraper(page, data)
    catalogs = scraper.open_form()
    tree = tree_from_catalogs(catalogs, set(data.audiences.values()))
    todo = [(node, path) for node, path in leaves(tree) if str(node["id"]) not in progress]
    total = len(leaves(tree))
    log.info("%d feuilles, %d déjà relevées", total, total - len(todo))
    for count, (node, path) in enumerate(todo[:limit] if limit else todo, start=1):
        try:
            progress[str(node["id"])] = scraper.sizes_of(path)
        except Exception:
            log.exception("Feuille %s (%s) non relevée", node["id"], node["label"])
            # Formulaire dans un état inconnu : on repart d'une page neuve.
            scraper.open_form()
            continue
        _progress_file().write_text(json.dumps(progress), encoding="utf-8")
        sizes = progress[str(node["id"])]
        done = total - len(todo) + count
        print(f"{done}/{total} {node['label']} : {len(sizes) if sizes else 'sans'} tailles")
    if scraper.colors is None:  # aucune feuille relevée cette fois : on en choisit une
        scraper.sizes_of(leaves(tree)[0][1])
    return {"catalog": tree, "colors": colors_from_response(scraper.colors)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data", type=Path, default=Path("data/vinted.json"))
    parser.add_argument("--limit", type=int, help="nombre de feuilles à relever cette fois")
    parser.add_argument("--restart", action="store_true", help="oublier le relevé en cours")
    args = parser.parse_args(argv)
    setup_logging(console=True)

    existing = json.loads(args.data.read_text(encoding="utf-8"))
    data = VintedData.model_validate(existing)
    progress_file = _progress_file()
    progress = {}
    if progress_file.is_file() and not args.restart:
        progress = json.loads(progress_file.read_text(encoding="utf-8"))

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        session = browser.open_context(pw)
        try:
            page = session.pages[0] if session.pages else session.new_page()
            if not browser.is_logged_in(page, data):
                print("Connecte d'abord le vendeur de test dans l'app (fenêtre Vinted).")
                return 1
            scraped = scrape(page, data, progress, args.limit)
        finally:
            session.close()

    missing = [n["id"] for n, _ in leaves(scraped["catalog"]) if str(n["id"]) not in progress]
    if missing:
        print(f"{len(missing)} feuilles restent à relever : relancer la commande.")
        return 2
    scraped["sizes"] = {int(k): v for k, v in progress.items()}
    merged = merge(existing, scraped, date.today())
    args.data.write_text(
        json.dumps(merged, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    progress_file.unlink()
    print(f"{args.data} réécrit (révision {merged['revision']}) : relire le diff.")
    return 0
