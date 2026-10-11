"""Modèles de données du cœur."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

GarmentType = Literal[
    "haut", "robe", "jupe", "pantalon", "veste", "chaussures", "sac", "accessoire", "autre"
]

# Libellés du centre d'aide Vinted (vérifiés le 2026-10-10). À confronter au formulaire
# réel dans le sous-projet 3 : certaines annonces affichent encore « Neuf avec étiquette ».
Condition = Literal["Neuf", "Comme neuf", "Très bon état", "Bon état", "Satisfaisant"]

ParcelSize = Literal["Petit", "Moyen", "Grand"]

Audience = Literal["femme", "homme", "enfant"]


class ArticleStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    GENERATING = "generating"
    TO_REVIEW = "to_review"
    VALIDATED = "validated"
    PUBLISHED = "published"
    ERROR = "error"


class UserInput(BaseModel):
    """Informations saisies par le client ; seul le type est obligatoire."""

    garment_type: GarmentType
    audience: Audience | None = None
    brand: str | None = None
    size: str | None = None
    condition: Condition | None = None
    color: str | None = None
    price: float | None = None
    notes: str | None = None


class Listing(BaseModel):
    """Annonce générée ; aussi utilisé comme schéma de sortie structurée pour Gemini."""

    title: str
    description: str
    category: str | None = None  # identifiant de catégorie Vinted, ex. "1779"
    brand: str | None = None
    size: str | None = None
    condition: Condition | None = None
    color: list[str] = Field(default=[], max_length=2)  # couleurs Vinted
    price: float | None = None
    parcel_size: ParcelSize | None = None

    @field_validator("category", mode="before")
    @classmethod
    def _category_is_vinted_id(cls, value):
        # Avant le sous-projet 3, la catégorie était un texte libre : on l'oublie.
        if isinstance(value, str) and not value.isdigit():
            return None
        return value

    @field_validator("color", mode="before")
    @classmethod
    def _color_from_text(cls, value):
        # Ancien format : une couleur en texte libre.
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        return value


class ListingChoices(BaseModel):
    """Valeurs Vinted proposées à Gemini pour l'annonce d'un article."""

    categories: dict[str, str]  # id → chemin lisible
    colors: list[str]


class VintedResult(BaseModel):
    mode: Literal["draft", "publish"]  # action réellement effectuée
    status: Literal["ok", "partial", "error"]
    missing_fields: list[str] = []  # libellés français : « Marque », « Taille »…
    url: str | None = None
    error: str | None = None  # message client, en français
    sent_at: datetime


class SceneResult(BaseModel):
    scene: str
    status: Literal["pending", "ok", "error"] = "pending"
    image: str | None = None
    error: str | None = None
    excluded: bool = False


class GenerationJob(BaseModel):
    """Demande de génération en attente ; persistée pour reprendre la file après un arrêt."""

    scene_slugs: list[str] | None = None  # None = toutes les scènes actives
    regenerate_listing: bool = False
    queued_at: datetime


class Article(BaseModel):
    id: str
    created_at: datetime
    status: ArticleStatus = ArticleStatus.DRAFT
    input: UserInput
    photos: list[str] = []
    scenes: list[SceneResult] = []
    listing: Listing | None = None
    error: str | None = None
    job: GenerationJob | None = None
    # Images à envoyer sur Vinted, dans l'ordre (relatives au dossier de l'article).
    # None = images des scènes réussies non exclues, dans l'ordre des scènes.
    gallery: list[str] | None = None
    vinted: VintedResult | None = None
