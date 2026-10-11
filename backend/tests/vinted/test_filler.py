"""Remplissage sur une page factice qui reproduit la structure de vinted.fr (relevé du 2026-10-11).

Les localisateurs utilisés sont ceux de la copie embarquée : la page factice les valide aussi.
"""

import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from vto.core import paths, storage
from vto.core.models import ArticleStatus, Listing, SceneResult
from vto.vinted import remote
from vto.vinted.catalog import Catalog
from vto.vinted.filler import (
    PAGE_ERROR,
    SAVE_ERROR,
    Timing,
    fill_item,
    format_price,
    normalize,
    size_tab,
)
from vto.vinted.schema import VintedData

FIXTURES = Path(__file__).parent / "fixtures"
FAST = Timing(page=5000, step=3000, optional=300, photos=5000, save=5000, pause=(0, 0))


# --- Sans navigateur ---------------------------------------------------------------------


@pytest.mark.parametrize(("price", "text"), [(12.5, "12,50"), (8, "8,00"), (0.99, "0,99")])
def test_format_price(price, text):
    assert format_price(price) == text


def test_normalize():
    assert normalize(" Sézane ") == normalize("sezane")
    assert normalize("H&M") == "h&m"


@pytest.mark.parametrize(
    ("size", "tab"),
    [("FR 38", "FR"), ("FR 38", "FR"), ("EU 40", "EU"), ("M", None), ("W30 | FR 40", None)],
)
def test_size_tab(size, tab):
    assert size_tab(size) == tab


def test_condition_and_parcel_labels_come_from_data():
    data = VintedData.model_validate_json(remote.bundled_text())
    assert data.conditions["Neuf"] == "Neuf avec étiquette"
    assert data.conditions["Comme neuf"] == "Neuf sans étiquette"
    assert data.parcel_sizes["Petit"] == "Petit"


# --- Avec navigateur ---------------------------------------------------------------------


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def site():
    handler = functools.partial(QuietHandler, directory=str(FIXTURES))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as pw:
        launched = None
        for options in ({"channel": "chrome"}, {}):
            try:
                launched = pw.chromium.launch(headless=True, **options)
                break
            except Error:
                continue
        if launched is None:
            pytest.skip("aucun navigateur pour Playwright")
        yield launched
        launched.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    yield context.new_page()
    context.close()


def site_data(site: str, query: str = "") -> VintedData:
    raw = json.loads(remote.bundled_text())
    raw["urls"] = {"home": site, "new_item": f"{site}/items/new.html{query}"}
    return VintedData.model_validate(raw)


@pytest.fixture
def article(data_dir, make_article, make_image):
    article = make_article("robe", audience="femme")
    folder = paths.article_dir(article.id)
    make_image(folder / "generated" / "mannequin.jpg")
    article.scenes = [SceneResult(scene="mannequin", status="ok", image="generated/mannequin.jpg")]
    article.gallery = ["generated/mannequin.jpg", "photos/001.jpg"]
    article.listing = Listing(
        title="Robe Zara M noire",
        description="Jolie robe portée deux fois.",
        category="178",
        brand="zara",
        size="M",
        condition="Très bon état",
        color=["Noir", "Bleu"],
        price=12.5,
        parcel_size="Petit",
    )
    article.status = ArticleStatus.VALIDATED
    storage.save(article)
    return article


def fill(page, article, site, mode="draft", query=""):
    data = site_data(site, query)
    report = fill_item(page, article, data, Catalog(data), mode, timing=FAST)
    saved = page.evaluate("() => JSON.parse(sessionStorage.getItem('saved'))")
    return report, saved


pytestmark_browser = pytest.mark.browser


@pytestmark_browser
def test_complete_draft(page, article, site):
    report, saved = fill(page, article, site)
    assert (report.status, report.mode, report.missing_fields) == ("ok", "draft", [])
    assert report.url == f"{site}/items/8/edit"  # lien du brouillon lu sur le profil
    assert saved["mode"] == "draft"
    assert saved["photos"] == ["mannequin.jpg", "001.jpg"]  # ordre de la galerie
    assert saved["ai"] is True  # la galerie contient une image générée
    assert saved["title"] == "Robe Zara M noire"
    assert saved["description"] == "Jolie robe portée deux fois."
    assert saved["category"] == 178
    assert saved["brand"] == "Zara"  # « zara » saisi : casse ignorée
    assert saved["size"] == "M"
    assert saved["condition"] == "Très bon état"
    assert saved["colors"] == ["Noir", "Bleu"]
    assert saved["price"] == "12,50"
    assert saved["parcel"] == "Petit"


@pytestmark_browser
def test_complete_publish(page, article, site):
    report, saved = fill(page, article, site, mode="publish")
    assert (report.status, report.mode) == ("ok", "publish")
    assert saved["mode"] == "publish"
    assert report.url == f"{site}/items/99.html"


@pytestmark_browser
def test_missing_category_saves_draft_even_in_publish_mode(page, article, site):
    report, saved = fill(page, article, site, mode="publish", query="?nocategory")
    assert report.status == "partial"
    assert report.missing_fields == ["Catégorie"]
    assert report.mode == "draft" and saved["mode"] == "draft"
    assert saved["brand"] == "Zara"  # les autres champs sont remplis


@pytestmark_browser
@pytest.mark.parametrize("category", ["157", "1056"])  # autre branche, catégorie voisine
def test_category_already_suggested_by_vinted(page, article, site, category):
    # Vinted présélectionne une catégorie d'après les photos : la liste s'ouvre à son niveau.
    article.listing.category = category
    report, saved = fill(page, article, site, query="?preselect")
    assert "Catégorie" not in report.missing_fields
    assert saved["category"] == int(category)


@pytestmark_browser
@pytest.mark.parametrize(("brand", "expected"), [("SEZANE", "Sézane"), ("Sézane", "Sézane")])
def test_brand_ignores_case_and_accents(page, article, site, brand, expected):
    article.listing.brand = brand
    report, saved = fill(page, article, site)
    assert report.missing_fields == []
    assert saved["brand"] == expected


@pytestmark_browser
def test_popup_after_brand_is_closed(page, article, site):
    # « Preuves d'authenticité » s'ouvre après le choix de certaines marques et bloque le reste.
    report, saved = fill(page, article, site, query="?authenticity")
    assert report.missing_fields == []
    assert saved["size"] == "M" and saved["colors"] == ["Noir", "Bleu"]


@pytestmark_browser
def test_brand_list_not_opened_by_first_click(page, article, site):
    report, saved = fill(page, article, site, query="?brandlate")
    assert report.missing_fields == []
    assert saved["brand"] == "Zara"


@pytestmark_browser
def test_brand_without_identical_suggestion(page, article, site):
    article.listing.brand = "Zarra"
    report, saved = fill(page, article, site)
    assert report.missing_fields == ["Marque"]
    assert saved["brand"] is None
    assert saved["size"] == "M"  # la liste des marques a été refermée


@pytestmark_browser
def test_category_without_grid_skips_size(page, article, site):
    article.listing.category = "157"  # sacs à dos
    report, saved = fill(page, article, site)
    assert report.missing_fields == []
    assert saved["category"] == 157 and saved["size"] is None


@pytestmark_browser
def test_size_in_another_tab(page, article, site):
    article.listing.size = "FR 38"  # espace normale ; Vinted écrit une espace insécable
    report, saved = fill(page, article, site)
    assert report.missing_fields == []
    assert saved["size"] == "FR 38"


@pytestmark_browser
def test_size_out_of_grid(page, article, site):
    article.listing.size = "38 ans"
    report, saved = fill(page, article, site)
    assert report.missing_fields == ["Taille"]
    assert saved["size"] is None


@pytestmark_browser
def test_unknown_color(page, article, site):
    article.listing.color = ["Noir", "Bleu canard"]
    report, saved = fill(page, article, site)
    assert report.missing_fields == ["Couleur"]
    assert saved["colors"] == ["Noir"]


@pytestmark_browser
def test_no_ai_mention_without_generated_image(page, article, site):
    article.gallery = ["photos/001.jpg"]
    report, saved = fill(page, article, site)
    assert report.status == "ok"
    assert saved["ai"] is False


@pytestmark_browser
def test_save_button_missing_is_an_error(page, article, site):
    data = site_data(site, "?nosave")
    report = fill_item(page, article, data, Catalog(data), "draft", timing=FAST)
    assert report.status == "error"
    assert report.error == SAVE_ERROR


@pytestmark_browser
def test_page_not_loading_is_an_error(page, article, site):
    data = site_data(site)
    urls = data.urls.model_copy(update={"new_item": f"{site}/rien.html"})
    data = data.model_copy(update={"urls": urls})
    report = fill_item(page, article, data, Catalog(data), "draft", timing=FAST)
    assert (report.status, report.error) == ("error", PAGE_ERROR)


@pytestmark_browser
def test_screenshot_for_each_missing_field(page, article, site):
    article.listing.brand = "Zarra"
    article.listing.color = ["Bleu canard"]
    fill(page, article, site)
    shots = sorted(p.name for p in paths.vinted_log_dir().glob("*.png"))
    assert len(shots) == 2
    assert any("marque" in s for s in shots) and any("couleur" in s for s in shots)
