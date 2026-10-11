import copy

import pytest
from pydantic import ValidationError

from vto.vinted.schema import (
    REQUIRED_LOCATORS,
    CssLocator,
    LabelLocator,
    RoleLocator,
    TextLocator,
    VintedData,
)


def minimal() -> dict:
    """Plus petit fichier valide : tous les localisateurs requis, un arbre à deux niveaux."""
    return {
        "format": 1,
        "revision": "2026-10-11.1",
        "urls": {"home": "https://www.vinted.fr", "new_item": "https://www.vinted.fr/items/new"},
        "locators": {name: [{"css": f"#{name}"}] for name in REQUIRED_LOCATORS},
        "catalog": [
            {
                "id": 1904,
                "label": "Femmes",
                "children": [
                    {"id": 1779, "label": "Robes", "size_group": "4", "garment_types": ["robe"]},
                    {"id": 1800, "label": "Sacs"},
                ],
            },
            {"id": 5, "label": "Hommes", "children": []},
        ],
        "size_groups": {"4": ["XS", "S", "M"]},
        "conditions": {"Neuf": "Neuf avec étiquette", "Bon état": "Bon état"},
        "colors": ["Noir", "Blanc"],
        "parcel_sizes": {"Petit": "Petit"},
        "audiences": {"femme": 1904, "homme": 5},
    }


def test_minimal_file_is_valid():
    data = VintedData.model_validate(minimal())
    assert data.revision == "2026-10-11.1"
    assert data.catalog[0].children[0].garment_types == ["robe"]
    assert data.catalog[0].children[1].size_group is None
    assert data.audiences["femme"] == 1904


def test_locator_forms():
    raw = minimal()
    raw["locators"]["title"] = [
        {"css": "[data-testid='title--input']"},
        {"label": "Titre"},
        {"text": "{label}"},
        {"role": "button", "name": "{label}"},
    ]
    alternatives = VintedData.model_validate(raw).locators["title"]
    assert [type(a) for a in alternatives] == [CssLocator, LabelLocator, TextLocator, RoleLocator]
    assert alternatives[3].name == "{label}"


def test_extra_locator_names_are_kept():
    # Un fichier plus récent peut ajouter des localisateurs : l'app les ignore.
    raw = minimal()
    raw["locators"]["nouveau"] = [{"css": "#x"}]
    assert "nouveau" in VintedData.model_validate(raw).locators


def mutate(path, value=None, *, delete=False):
    raw = copy.deepcopy(minimal())
    target = raw
    for key in path[:-1]:
        target = target[key]
    if delete:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return raw


INVALID = {
    "champ inconnu": mutate(["inconnu"], 1),
    "champ inconnu dans un nœud": mutate(["catalog", 0, "couleur"], "rouge"),
    "format 2": mutate(["format"], 2),
    "ids dupliqués": mutate(["catalog", 0, "children", 1, "id"], 1779),
    "id dupliqué entre racines": mutate(["catalog", 1, "id"], 1779),
    "size_group inexistant": mutate(["catalog", 0, "children", 0, "size_group"], "99"),
    "état hors du cœur": mutate(["conditions", "Neuf avec étiquette"], "x"),
    "colis hors du cœur": mutate(["parcel_sizes", "Énorme"], "x"),
    "localisateur requis absent": mutate(["locators", "save_draft"], delete=True),
    "localisateur vide": mutate(["locators", "title"], []),
    "alternative sans forme": mutate(["locators", "title"], [{}]),
    "alternative à deux formes": mutate(["locators", "title"], [{"css": "#a", "label": "b"}]),
    "forme inconnue": mutate(["locators", "title"], [{"xpath": "//a"}]),
    "role sans name": mutate(["locators", "title"], [{"role": "button"}]),
    "type de vêtement inconnu": mutate(["catalog", 0, "garment_types"], ["chapeau"]),
    "public hors des racines": mutate(["audiences", "enfant"], 1779),
    "public inconnu": mutate(["audiences", "bébé"], 1904),
    "grille vide": mutate(["size_groups", "4"], []),
    "aucune couleur": mutate(["colors"], []),
    "catalogue vide": mutate(["catalog"], []),
}


@pytest.mark.parametrize("raw", INVALID.values(), ids=INVALID.keys())
def test_invalid_files_are_rejected(raw):
    with pytest.raises(ValidationError):
        VintedData.model_validate(raw)
