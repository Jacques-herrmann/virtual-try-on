"""Outil de relevé du catalogue : lecture des réponses de Vinted et fusion, sans navigateur."""

import json
from datetime import date

import pytest

from vto.tools.vinted_catalog import (
    colors_from_response,
    leaves,
    merge,
    next_revision,
    sizes_from_attributes,
    tree_from_catalogs,
)
from vto.vinted import remote
from vto.vinted.schema import VintedData

TODAY = date(2026, 10, 12)


def node(id_, label, *children):
    return {"id": id_, "label": label, "children": list(children)}


@pytest.fixture
def existing():
    data = json.loads(remote.bundled_text())
    data["revision"] = "2026-10-11.4"
    data["catalog"] = [
        {"id": 1904, "label": "Femmes", "children": [
            {"id": 10, "label": "Robes", "garment_types": ["robe"], "children": [
                {"id": 178, "label": "Mini", "size_group": "lettres"},
                {"id": 999, "label": "Disparue", "size_group": "lettres"},
            ]},
        ]},
        {"id": 5, "label": "Hommes", "children": [{"id": 77, "label": "Sacs"}]},
    ]
    data["size_groups"] = {"lettres": ["S", "M", "L"], "inutilisee": ["36"]}
    data["audiences"] = {"femme": 1904, "homme": 5}
    return data


def test_tree_keeps_only_wanted_roots():
    body = {"catalogs": [
        {"id": 1904, "title": "Femmes", "catalogs": [
            {"id": 10, "title": "Robes ", "catalogs": []},
        ]},
        {"id": 2994, "title": "Maison", "catalogs": []},
    ]}
    assert tree_from_catalogs(body, {1904}) == [node(1904, "Femmes", node(10, "Robes"))]


def test_sizes_flatten_tabs_in_order():
    body = {"attributes": [
        {"code": "brand", "configuration": None},
        {"code": "size", "configuration": {"options": [
            {"type": "group", "title": "S/M/L", "options": [
                {"type": "default", "title": "S"}, {"type": "default", "title": "M"},
            ]},
            {"type": "group", "title": "FR", "options": [{"type": "default", "title": "FR 38"}]},
        ]}},
    ]}
    assert sizes_from_attributes(body) == ["S", "M", "FR 38"]


def test_no_size_field():
    assert sizes_from_attributes({"attributes": [{"code": "brand"}]}) is None


def test_colors_in_vinted_order():
    body = {"colors": [{"title": "Gris", "order": 2}, {"title": "Noir", "order": 1}]}
    assert colors_from_response(body) == ["Noir", "Gris"]


def test_leaves_with_path():
    tree = [node(1, "A", node(2, "B", node(3, "C")), node(4, "D"))]
    assert [(n["id"], p) for n, p in leaves(tree)] == [(3, [1, 2, 3]), (4, [1, 4])]


@pytest.mark.parametrize(
    ("revision", "expected"),
    [("2026-10-12.3", "2026-10-12.4"), ("2026-10-11.4", "2026-10-12.1"), ("essai", "2026-10-12.1")],
)
def test_next_revision(revision, expected):
    assert next_revision(revision, TODAY) == expected


def scraped(sizes):
    return {
        "catalog": [
            node(1904, "Femmes", node(10, "Robes", node(178, "Mini"), node(1056, "Midi"))),
            node(5, "Hommes", node(77, "Sacs")),
        ],
        "sizes": sizes,
        "colors": ["Noir", "Blanc"],
    }


def test_merge(existing):
    merged = merge(existing, scraped({178: ["S", "M", "L"], 1056: ["XS", "S"], 77: None}), TODAY)
    VintedData.model_validate(merged)
    femmes, hommes = merged["catalog"]
    robes = femmes["children"][0]
    assert robes["garment_types"] == ["robe"]  # gardé sur l'id existant
    assert [c["id"] for c in robes["children"]] == [178, 1056]  # 999 disparue, 1056 nouvelle
    mini, midi = robes["children"]
    assert mini["size_group"] == "lettres"  # grille identique : même nom
    assert "garment_types" not in midi  # nouveau nœud sans type (hérité de Robes)
    assert merged["size_groups"][midi["size_group"]] == ["XS", "S"]
    assert "size_group" not in hommes["children"][0]  # pas de taille
    assert "inutilisee" not in merged["size_groups"]
    assert merged["colors"] == ["Noir", "Blanc"]
    assert merged["revision"] == "2026-10-12.1"
    assert merged["locators"] == existing["locators"]  # maintenus à la main
    assert merged["audiences"] == existing["audiences"]


def test_merge_names_new_grids_without_collision(existing):
    merged = merge(existing, scraped({178: ["XS"], 1056: ["XL"], 77: None}), TODAY)
    mini, midi = merged["catalog"][0]["children"][0]["children"]
    assert mini["size_group"] != midi["size_group"]
    assert mini["size_group"].startswith("femmes-robes")


def test_merge_refuses_invalid_result(existing):
    existing["audiences"]["enfant"] = 1193  # racine absente du relevé
    with pytest.raises(ValueError):
        merge(existing, scraped({178: None, 1056: None, 77: None}), TODAY)
