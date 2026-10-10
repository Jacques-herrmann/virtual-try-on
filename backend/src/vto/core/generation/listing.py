"""Génération de l'annonce d'un article."""

from vto.core import paths
from vto.core.config import Settings
from vto.core.generation.client import GenAIClient
from vto.core.images import load_image, resize_max
from vto.core.models import Article, Listing

# Champs saisis par le client qui priment sur la proposition du modèle.
OVERRIDABLE = ("brand", "size", "condition", "color", "price")

LABELS = {
    "garment_type": "Type",
    "brand": "Marque",
    "size": "Taille",
    "condition": "État",
    "color": "Couleur",
    "price": "Prix souhaité",
    "notes": "Notes",
}


def _known_info(article: Article) -> str:
    values = article.input.model_dump()
    lines = [f"- {label} : {values[key]}" for key, label in LABELS.items() if values[key]]
    return "Informations connues sur le vêtement :\n" + "\n".join(lines)


def generate_listing(client: GenAIClient, settings: Settings, article: Article) -> Listing:
    article_dir = paths.article_dir(article.id)
    image_paths = [s.image for s in article.scenes if s.status == "ok" and s.image][:1]
    image_paths.append(article.photos[0])
    images = [resize_max(load_image(article_dir / p)) for p in image_paths]

    prompt = f"{settings.listing_prompt.rstrip()}\n\n{_known_info(article)}"
    listing = client.generate_json(settings.text_model, prompt, images, Listing)

    for field in OVERRIDABLE:
        value = getattr(article.input, field)
        if value is not None:
            setattr(listing, field, value)
    if settings.signature.strip():
        listing.description = f"{listing.description.rstrip()}\n\n{settings.signature.strip()}"
    return listing
