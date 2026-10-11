"""Génération de l'annonce d'un article."""

from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import Field, WithJsonSchema, create_model

from vto.core import paths
from vto.core.config import Settings
from vto.core.generation.client import GenAIClient
from vto.core.images import load_image, resize_max
from vto.core.models import Article, Listing, ListingChoices

# Champs saisis par le client qui priment sur la proposition du modèle. La couleur saisie
# n'est qu'une indication : l'annonce doit utiliser les couleurs de Vinted.
OVERRIDABLE = ("brand", "size", "condition", "price")

LABELS = {
    "garment_type": "Type",
    "audience": "Public",
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


def _one_of(values: Sequence[str]):
    # Toujours un `enum` dans le schéma (pydantic écrirait `const` pour une seule valeur).
    return Annotated[
        Literal[tuple(values)], WithJsonSchema({"type": "string", "enum": list(values)})
    ]


def _constrained_schema(choices: ListingChoices) -> type[Listing]:
    """`Listing` dont la catégorie et les couleurs sont limitées aux valeurs proposées."""
    # Sans valeur proposée, le champ reste vide.
    category = _one_of(list(choices.categories)) | None if choices.categories else None
    color = _one_of(choices.colors) if choices.colors else str
    return create_model(
        "VintedListing",
        __base__=Listing,
        category=(category, None),
        color=(list[color], Field(default=[], max_length=2 if choices.colors else 0)),
    )


def _choices_text(choices: ListingChoices) -> str:
    lines = ["Catégories possibles (donne l'identifiant de la plus précise) :"]
    lines += [f"- {cat_id} : {label}" for cat_id, label in choices.categories.items()]
    lines.append(f"Couleurs possibles (deux au plus) : {', '.join(choices.colors)}")
    return "\n".join(lines)


def generate_listing(
    client: GenAIClient,
    settings: Settings,
    article: Article,
    choices: ListingChoices | None = None,
) -> Listing:
    """Annonce de l'article. Avec `choices`, catégorie et couleurs sont prises dans Vinted."""
    article_dir = paths.article_dir(article.id)
    image_paths = [s.image for s in article.scenes if s.status == "ok" and s.image][:1]
    image_paths.append(article.photos[0])
    images = [resize_max(load_image(article_dir / p)) for p in image_paths]

    prompt = f"{settings.listing_prompt.rstrip()}\n\n{_known_info(article)}"
    schema = Listing
    if choices is not None:
        prompt = f"{prompt}\n\n{_choices_text(choices)}"
        schema = _constrained_schema(choices)
    output = client.generate_json(settings.text_model, prompt, images, schema)
    listing = Listing.model_validate(output.model_dump())

    for field in OVERRIDABLE:
        value = getattr(article.input, field)
        if value is not None:
            setattr(listing, field, value)
    if settings.signature.strip():
        listing.description = f"{listing.description.rstrip()}\n\n{settings.signature.strip()}"
    return listing
