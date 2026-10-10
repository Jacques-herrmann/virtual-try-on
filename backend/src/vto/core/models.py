"""Modèles de données du cœur."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

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
    category: str | None = None
    brand: str | None = None
    size: str | None = None
    condition: Condition | None = None
    color: str | None = None
    price: float | None = None
    parcel_size: ParcelSize | None = None


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
