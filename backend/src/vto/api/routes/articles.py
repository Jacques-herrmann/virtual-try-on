from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel

from vto.api.uploads import received_images
from vto.core import scenes, storage
from vto.core.errors import VtoError
from vto.core.models import (
    Article,
    ArticleStatus,
    Audience,
    Condition,
    GarmentType,
    Listing,
    UserInput,
)

router = APIRouter(prefix="/api/articles")

S = ArticleStatus


class GenerateRequest(BaseModel):
    scenes: list[str] | None = None
    listing: bool = False


class ExcludeRequest(BaseModel):
    excluded: bool


@router.get("")
def list_articles(status: ArticleStatus | None = None) -> list[Article]:
    found = [a for a in storage.list_articles() if status is None or a.status == status]
    return sorted(found, key=lambda a: a.created_at, reverse=True)


@router.post("", status_code=201)
def create_article(
    request: Request,
    garment_type: Annotated[GarmentType, Form()],
    audience: Annotated[Audience | None, Form()] = None,
    brand: Annotated[str | None, Form()] = None,
    size: Annotated[str | None, Form()] = None,
    condition: Annotated[Condition | None, Form()] = None,
    color: Annotated[str | None, Form()] = None,
    price: Annotated[float | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
    photos: Annotated[list[UploadFile] | None, File()] = None,
) -> Article:
    if not photos:
        raise VtoError("Ajoute au moins une photo du vêtement.")
    data = UserInput(
        garment_type=garment_type,
        audience=audience,
        brand=brand,
        size=size,
        condition=condition,
        color=color,
        price=price,
        notes=notes,
    )
    with received_images(photos) as received:
        article = storage.create_article(data, [path for path, _ in received])
    return request.app.state.queue.enqueue(article.id)


@router.get("/{article_id}")
def get_article(article_id: str) -> Article:
    return storage.load(article_id)


@router.patch("/{article_id}/input")
def update_input(article_id: str, user_input: UserInput) -> Article:
    article = storage.load(article_id)
    storage.update_input(article, user_input)
    return article


@router.patch("/{article_id}/listing")
def update_listing(article_id: str, listing: Listing) -> Article:
    article = storage.load(article_id)
    storage.update_listing(article, listing)
    return article


@router.patch("/{article_id}/scenes/{slug}")
def set_excluded(article_id: str, slug: str, body: ExcludeRequest) -> Article:
    article = storage.load(article_id)
    storage.set_excluded(article, slug, body.excluded)
    return article


@router.post("/{article_id}/generate")
def generate(request: Request, article_id: str, body: GenerateRequest | None = None) -> Article:
    """Sans corps : tout régénérer. `scenes` : ces images-là. `listing` : l'annonce."""
    body = body or GenerateRequest()
    if body.scenes is None:
        scene_slugs = [] if body.listing else None
    else:
        available = {s.slug for s in scenes.list_scenes()}
        unknown = [s for s in body.scenes if s not in available]
        if unknown:
            raise VtoError(f"Scène inconnue ou désactivée : {', '.join(unknown)}.")
        scene_slugs = body.scenes
    return request.app.state.queue.enqueue(
        article_id, scene_slugs=scene_slugs, regenerate_listing=body.listing
    )


@router.post("/{article_id}/cancel")
def cancel(request: Request, article_id: str) -> Article:
    request.app.state.queue.cancel(article_id)
    return storage.load(article_id)


@router.post("/{article_id}/validate")
def validate(article_id: str) -> Article:
    article = storage.load(article_id)
    storage.set_status(article, S.VALIDATED)
    return article


@router.post("/{article_id}/unvalidate")
def unvalidate(article_id: str) -> Article:
    article = storage.load(article_id)
    storage.set_status(article, S.TO_REVIEW)
    return article


@router.delete("/{article_id}", status_code=204)
def delete_article(article_id: str) -> Response:
    article = storage.load(article_id)
    if article.status in (S.QUEUED, S.GENERATING):
        raise HTTPException(
            409, "Impossible de supprimer un article en cours de génération. Annule-le d'abord."
        )
    storage.delete(article.id)
    return Response(status_code=204)
