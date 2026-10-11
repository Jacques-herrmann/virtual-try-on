from datetime import UTC, datetime

import pytest

from samples import minimal
from vto.core.models import Article, UserInput
from vto.vinted.catalog import Catalog
from vto.vinted.schema import VintedData


def leaf(id, label, **kw):
    return {"id": id, "label": label, **kw}


@pytest.fixture
def catalog() -> Catalog:
    raw = minimal()
    raw["catalog"] = [
        leaf(1904, "Femmes", children=[
            leaf(4, "Vêtements", children=[
                leaf(10, "Robes", garment_types=["robe"], children=[
                    leaf(1779, "Mini", size_group="4"),
                    leaf(1780, "Longues", size_group="4"),
                    leaf(1781, "Robes-chemises", garment_types=["robe", "haut"]),
                ]),
                leaf(12, "Hauts", garment_types=["haut"], children=[
                    leaf(1806, "T-shirts", size_group="4"),
                ]),
            ]),
            leaf(1800, "Sacs", garment_types=["sac"]),
            leaf(1900, "Divers"),
        ]),
        leaf(5, "Hommes", children=[
            leaf(2001, "T-shirts", garment_types=["haut"], size_group="4"),
            leaf(2002, "Autres"),
        ]),
    ]
    return Catalog(VintedData.model_validate(raw))


def ids(nodes):
    return [n.id for n in nodes]


def test_path(catalog):
    assert catalog.path("1779") == ["Femmes", "Vêtements", "Robes", "Mini"]
    assert catalog.path(2001) == ["Hommes", "T-shirts"]


@pytest.mark.parametrize("unknown", ["999", 999, "Robes", "", None])
def test_path_unknown(catalog, unknown):
    assert catalog.path(unknown) is None


@pytest.mark.parametrize(
    ("garment", "audience", "expected"),
    [
        ("robe", "femme", [1779, 1780, 1781]),
        ("haut", "femme", [1781, 1806]),  # hérité de « Hauts », ou propre à la feuille
        ("haut", "homme", [2001]),
        ("haut", None, [1781, 1806, 2001]),  # public inconnu : toutes les racines
        ("haut", "enfant", [1781, 1806, 2001]),  # public absent des données : idem
        ("sac", "femme", [1800]),
        ("autre", "femme", [1900]),  # feuilles sans type hérité
        ("autre", None, [1900, 2002]),
        ("chaussures", "femme", []),
    ],
)
def test_leaves_for(catalog, garment, audience, expected):
    assert ids(catalog.leaves_for(garment, audience)) == expected


def test_is_leaf(catalog):
    assert catalog.is_leaf("1779") and catalog.is_leaf(1900)
    assert not catalog.is_leaf("10")  # « Robes » a des sous-catégories
    assert not catalog.is_leaf("999") and not catalog.is_leaf(None)


def test_sizes(catalog):
    assert catalog.sizes("1779") == ["XS", "S", "M"]
    assert catalog.sizes("1781") == []  # feuille sans grille
    assert catalog.sizes("999") == []
    assert catalog.sizes(None) == []


def test_choices_for(catalog):
    article = Article(
        id="a",
        created_at=datetime(2026, 10, 11, tzinfo=UTC),
        input=UserInput(garment_type="haut", audience="homme"),
    )
    choices = catalog.choices_for(article)
    assert choices.categories == {"2001": "Hommes › T-shirts"}
    assert choices.colors == ["Noir", "Blanc"]
