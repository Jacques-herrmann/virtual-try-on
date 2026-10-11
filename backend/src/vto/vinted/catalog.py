"""Arbre des catégories Vinted : chemins, feuilles proposées à Gemini, grilles de tailles."""

from dataclasses import dataclass

from vto.core.models import Article, Audience, GarmentType, ListingChoices
from vto.vinted.schema import CategoryNode, VintedData

SEPARATOR = " › "


@dataclass(frozen=True)
class _Entry:
    node: CategoryNode
    path: tuple[str, ...]
    root: int
    garment_types: tuple[str, ...] | None  # hérités du plus proche ancêtre qui en déclare


class Catalog:
    def __init__(self, data: VintedData):
        self.data = data
        self._entries: dict[int, _Entry] = {}
        for root in data.catalog:
            self._index(root, (), root.id, None)

    def _index(self, node, parent_path, root, inherited):
        types = tuple(node.garment_types) if node.garment_types is not None else inherited
        path = (*parent_path, node.label)
        self._entries[node.id] = _Entry(node, path, root, types)
        for child in node.children:
            self._index(child, path, root, types)

    def _entry(self, category_id: str | int | None) -> _Entry | None:
        if isinstance(category_id, str) and category_id.isdigit():
            category_id = int(category_id)
        if not isinstance(category_id, int):
            return None
        return self._entries.get(category_id)

    def path(self, category_id: str | int | None) -> list[str] | None:
        """Libellés de la racine à la catégorie, ou None si elle est inconnue."""
        entry = self._entry(category_id)
        return list(entry.path) if entry else None

    def is_leaf(self, category_id: str | int | None) -> bool:
        """Catégorie connue et sélectionnable (sans sous-catégorie)."""
        entry = self._entry(category_id)
        return entry is not None and not entry.node.children

    def sizes(self, category_id: str | int | None) -> list[str]:
        """Grille de tailles de la catégorie ; vide si elle n'en a pas."""
        entry = self._entry(category_id)
        if entry is None or entry.node.size_group is None:
            return []
        return list(self.data.size_groups[entry.node.size_group])

    def leaves_for(
        self, garment_type: GarmentType, audience: Audience | None
    ) -> list[CategoryNode]:
        """Feuilles à proposer pour ce type de vêtement, sous la racine du public s'il est connu.

        Une feuille sans type hérité n'est proposée que pour « autre ».
        """
        root = self.data.audiences.get(audience) if audience else None
        leaves = []
        for entry in self._entries.values():
            if entry.node.children or (root is not None and entry.root != root):
                continue
            if entry.garment_types is None:
                if garment_type == "autre":
                    leaves.append(entry.node)
            elif garment_type in entry.garment_types:
                leaves.append(entry.node)
        return leaves

    def choices_for(self, article: Article) -> ListingChoices:
        leaves = self.leaves_for(article.input.garment_type, article.input.audience)
        return ListingChoices(
            categories={str(n.id): SEPARATOR.join(self._entries[n.id].path) for n in leaves},
            colors=list(self.data.colors),
        )
