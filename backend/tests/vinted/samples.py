"""Données Vinted de test."""

from vto.vinted.schema import REQUIRED_LOCATORS


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
