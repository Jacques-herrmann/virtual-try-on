"""Remplissage du formulaire « Vendre un article » de vinted.fr."""

from dataclasses import dataclass, field
from typing import Literal

from vto.core.models import Article
from vto.vinted.catalog import Catalog
from vto.vinted.schema import VintedData

Mode = Literal["draft", "publish"]


@dataclass
class FillReport:
    mode: Mode  # action réellement effectuée
    status: Literal["ok", "partial", "error"]
    missing_fields: list[str] = field(default_factory=list)
    url: str | None = None
    error: str | None = None  # message client, en français


def fill_item(page, article: Article, data: VintedData, catalog: Catalog, mode: Mode) -> FillReport:
    raise NotImplementedError("Remplissage du formulaire : tâche 10 du plan Vinted.")
