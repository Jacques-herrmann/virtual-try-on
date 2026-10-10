"""Test de bout en bout contre la vraie API Gemini (payant, quelques centimes).

    GEMINI_API_KEY=... pytest -m live
"""

import os

import pytest
from PIL import Image, ImageDraw

from vto.core import config, paths, pipeline, scenes, storage
from vto.core.models import ArticleStatus, UserInput

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"), reason="GEMINI_API_KEY absente"),
]


def draw_tshirt(path):
    """T-shirt rouge à plat sur fond clair, dessiné pour éviter toute question de droits."""
    img = Image.new("RGB", (768, 1024), (235, 235, 230))
    d = ImageDraw.Draw(img)
    d.polygon(
        [(234, 200), (334, 170), (434, 170), (534, 200), (680, 330), (600, 420), (530, 360),
         (530, 850), (238, 850), (238, 360), (168, 420), (88, 330)],
        fill=(190, 30, 40),
    )
    d.ellipse((334, 150, 434, 230), fill=(235, 235, 230))
    img.save(path)
    return path


@pytest.fixture
def live_data_dir(tmp_path, monkeypatch):
    """Comme `data_dir`, mais garde GEMINI_API_KEY."""
    monkeypatch.setenv("VTO_DATA_DIR", str(tmp_path / "data"))


def test_full_article_with_real_api(live_data_dir, tmp_path):
    scenes.ensure_default_scenes()
    mannequin = paths.scenes_dir() / "mannequin" / "meta.json"
    cintre = paths.scenes_dir() / "cintre" / "meta.json"
    cintre.write_text(cintre.read_text(encoding="utf-8").replace("true", "false"), "utf-8")
    assert mannequin.is_file()

    article = storage.create_article(
        UserInput(garment_type="haut", audience="femme", brand="Sans marque", size="M"),
        [draw_tshirt(tmp_path / "tshirt.png")],
    )
    settings = config.load_settings()
    done = pipeline.process_article(
        article.id, client=pipeline.build_client(settings), settings=settings
    )

    assert done.status == ArticleStatus.TO_REVIEW, done.error or done.scenes
    image = paths.article_dir(article.id) / done.scenes[0].image
    with Image.open(image) as img:
        w, h = img.size
    assert h > w  # portrait 3:4
    assert done.listing.title and done.listing.description
    assert done.listing.size == "M"
    print("\nImage :", image, f"({w}x{h})")
    print(done.listing.model_dump_json(indent=2))
