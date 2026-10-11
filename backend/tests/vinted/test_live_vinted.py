"""Essai réel sur vinted.fr : crée un brouillon complet, le vérifie, puis l'efface.

Utilise le profil Chrome dédié de l'app, où le vendeur de test est déjà connecté
(sinon le test est ignoré). L'app ne doit pas avoir de fenêtre Vinted ouverte.

    pytest backend/tests -m live_vinted
"""

import pytest
from PIL import Image, ImageDraw

from vto.core import paths, storage
from vto.core.models import ArticleStatus, Listing
from vto.vinted import browser, remote
from vto.vinted.catalog import Catalog
from vto.vinted.filler import Timing, fill_item

pytestmark = pytest.mark.live_vinted

LISTING = Listing(
    title="T-shirt noir uni M (test, ne pas acheter)",
    description="Brouillon créé par les tests automatiques. Il est effacé aussitôt.",
    category="1806",  # Hommes › Vêtements › Hauts et t-shirts › T-shirts › T-shirts unis
    brand="Zara",
    size="M",
    condition="Très bon état",
    color=["Noir"],
    price=10,
    parcel_size="Petit",
)


@pytest.fixture
def real_profile():
    """Profil du navigateur dédié, lu avant que `data_dir` isole le reste des données."""
    return paths.browser_profile_dir()


@pytest.fixture
def article(real_profile, data_dir, monkeypatch, make_article):
    monkeypatch.setattr(paths, "browser_profile_dir", lambda: real_profile)
    article = make_article("haut", audience="homme")
    # Vinted refuse les toutes petites images : on en dessine une de taille normale.
    photo = paths.article_dir(article.id) / article.photos[0]
    img = Image.new("RGB", (768, 1024), (235, 235, 230))
    ImageDraw.Draw(img).rectangle((200, 200, 568, 850), fill=(20, 20, 20))
    img.save(photo)
    article.gallery = [article.photos[0]]
    article.listing = LISTING.model_copy(deep=True)
    article.status = ArticleStatus.VALIDATED
    storage.save(article)
    return article


def test_complete_draft_on_vinted(article):
    from playwright.sync_api import sync_playwright

    loaded = remote.load_vinted_data()
    data = loaded.data
    with sync_playwright() as pw:
        session = browser.open_context(pw)
        try:
            page = session.pages[0] if session.pages else session.new_page()
            if not browser.is_logged_in(page, data):
                pytest.skip("aucun compte Vinted connecté dans le profil de l'app")
            report = fill_item(page, article, data, Catalog(data), "draft", timing=Timing())
            try:
                assert report.error is None, report.error
                assert (report.status, report.mode, report.missing_fields) == ("ok", "draft", [])
                assert report.url and "/items/" in report.url
            finally:
                if report.url and "/items/" in report.url:
                    page.goto(report.url, wait_until="domcontentloaded")
                    page.get_by_test_id("upload-form-delete-draft-button").click(timeout=30_000)
                    page.wait_for_url("**/member/**", timeout=30_000)
        finally:
            session.close()
