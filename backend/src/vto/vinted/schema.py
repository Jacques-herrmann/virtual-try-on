"""Modèles de `vinted.json` : localisateurs, catalogue et libellés de vinted.fr.

Le fichier est téléchargé : ce ne sont que des données, validées strictement avant usage.
"""

from collections.abc import Iterator
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    Tag,
    model_validator,
)

from vto.core.models import Audience, Condition, GarmentType, ParcelSize

# Localisateurs dont le remplissage a besoin ; un fichier sans l'un d'eux est refusé.
REQUIRED_LOCATORS = (
    "logged_in",
    "cookie_accept",
    "popup_close",
    "photo_input",
    "photo_thumb",
    "ai_photo",
    "title",
    "description",
    "category_open",
    "category_option",
    "category_back",
    "brand_open",
    "brand_input",
    "brand_option",
    "brand_options",
    "size_open",
    "size_tab",
    "size_option",
    "condition_open",
    "condition_option",
    "color_open",
    "color_option",
    "color_close",
    "price",
    "parcel_option",
    "save_draft",
    "publish",
    "saved_marker",
    "draft_link",
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CssLocator(_Strict):
    css: str


class LabelLocator(_Strict):
    label: str


class TextLocator(_Strict):
    text: str


class RoleLocator(_Strict):
    role: str
    name: str


_FORMS = ("css", "label", "text", "role")


def _form(value) -> str | None:
    """Forme d'une alternative : sa seule clé parmi `_FORMS` (None si zéro ou plusieurs)."""
    if isinstance(value, BaseModel):
        value = value.model_dump()
    if not isinstance(value, dict):
        return None
    found = [form for form in _FORMS if form in value]
    return found[0] if len(found) == 1 else None


Locator = Annotated[
    Annotated[CssLocator, Tag("css")]
    | Annotated[LabelLocator, Tag("label")]
    | Annotated[TextLocator, Tag("text")]
    | Annotated[RoleLocator, Tag("role")],
    Discriminator(_form),
]

# Alternatives essayées dans l'ordre jusqu'à ce qu'une soit visible.
Alternatives = Annotated[list[Locator], Field(min_length=1)]


class Urls(_Strict):
    home: str
    new_item: str


class CategoryNode(_Strict):
    id: int
    label: str
    children: list["CategoryNode"] = []
    size_group: str | None = None  # feuilles uniquement ; absent = pas de taille
    garment_types: list[GarmentType] | None = None  # hérité par les descendants


# Numéro de format : change à chaque évolution incompatible ; il fait partie de l'URL distante.
FORMAT = 1


class VintedData(_Strict):
    format: Literal[1]  # = FORMAT
    revision: str
    urls: Urls
    locators: dict[str, Alternatives]
    catalog: Annotated[list[CategoryNode], Field(min_length=1)]
    size_groups: dict[str, Annotated[list[str], Field(min_length=1)]]
    conditions: dict[Condition, str]  # état du cœur → libellé Vinted
    colors: Annotated[list[str], Field(min_length=1)]
    parcel_sizes: dict[ParcelSize, str]  # taille du cœur → libellé Vinted
    audiences: dict[Audience, int]  # public → id de la racine du catalogue

    def nodes(self) -> Iterator[CategoryNode]:
        stack = list(reversed(self.catalog))
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children))

    @model_validator(mode="after")
    def _check_consistency(self):
        missing = [name for name in REQUIRED_LOCATORS if name not in self.locators]
        if missing:
            raise ValueError(f"localisateurs manquants : {', '.join(missing)}")
        seen: set[int] = set()
        for node in self.nodes():
            if node.id in seen:
                raise ValueError(f"id de catégorie dupliqué : {node.id}")
            seen.add(node.id)
            if node.size_group is not None and node.size_group not in self.size_groups:
                raise ValueError(f"grille de tailles inconnue : {node.size_group} ({node.id})")
        roots = {node.id for node in self.catalog}
        for audience, root in self.audiences.items():
            if root not in roots:
                raise ValueError(f"public {audience} : {root} n'est pas une racine du catalogue")
        return self
