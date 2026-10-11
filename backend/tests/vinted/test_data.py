from pathlib import Path

from vto.vinted import remote
from vto.vinted.catalog import Catalog
from vto.vinted.schema import REQUIRED_LOCATORS, VintedData

PUBLISHED = Path(__file__).parents[3] / "data" / "vinted.json"


def test_bundled_copy_matches_published_file():
    assert remote.bundled_text() == PUBLISHED.read_text(encoding="utf-8")


def test_bundled_copy_is_valid():
    data = VintedData.model_validate_json(remote.bundled_text())
    assert set(REQUIRED_LOCATORS) <= data.locators.keys()
    assert set(data.audiences) == {"femme", "homme", "enfant"}


def test_every_garment_type_has_categories():
    catalog = Catalog(VintedData.model_validate_json(remote.bundled_text()))
    for garment in ("haut", "robe", "jupe", "pantalon", "veste", "chaussures", "sac", "accessoire"):
        assert catalog.leaves_for(garment, "femme"), garment
