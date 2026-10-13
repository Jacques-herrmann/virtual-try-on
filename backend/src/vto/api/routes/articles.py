from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel

from vto.api.routes.vinted import require_catalog
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

# Le public choisit les décors des scènes et la branche du catalogue Vinted.
MISSING_AUDIENCE = "Choisis pour qui est le vêtement : Femme, Homme ou Enfant."

S = ArticleStatus


class GenerateRequest(BaseModel):
    scenes: list[str] | None = None
    listing: bool = False


class ExcludeRequest(BaseModel):
    excluded: bool


class GalleryRequest(BaseModel):
    gallery: list[str] | None


class ArticleView(Article):
    """Article renvoyé à l'interface, avec les photos qui partiront sur Vinted."""

    effective_gallery: list[str]


def view(article: Article) -> ArticleView:
    return ArticleView.model_validate(
        {**article.model_dump(), "effective_gallery": storage.effective_gallery(article)}
    )


@router.get("")
def list_articles(status: ArticleStatus | None = None) -> list[ArticleView]:
    found = [a for a in storage.list_articles() if status is None or a.status == status]
    return [view(a) for a in sorted(found, key=lambda a: a.created_at, reverse=True)]


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
) -> ArticleView:
    if audience is None:
        raise VtoError(MISSING_AUDIENCE)
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
    request.app.state.queue.check_licensed()
    with received_images(photos) as received:
        article = storage.create_article(data, [path for path, _ in received])
    return view(request.app.state.queue.enqueue(article.id))


@router.get("/{article_id}")
def get_article(article_id: str) -> ArticleView:
    return view(storage.load(article_id))


@router.patch("/{article_id}/input")
def update_input(article_id: str, user_input: UserInput) -> ArticleView:
    if user_input.audience is None:
        raise VtoError(MISSING_AUDIENCE)
    article = storage.load(article_id)
    storage.update_input(article, user_input)
    return view(article)


@router.patch("/{article_id}/listing")
def update_listing(request: Request, article_id: str, listing: Listing) -> ArticleView:
    if listing.category is not None and not require_catalog(request.app).is_leaf(
        listing.category
    ):
        raise HTTPException(422, "Cette catégorie n'existe pas sur Vinted. Choisis-en une autre.")
    article = storage.load(article_id)
    storage.update_listing(article, listing)
    return view(article)


@router.patch("/{article_id}/gallery")
def set_gallery(article_id: str, body: GalleryRequest) -> ArticleView:
    article = storage.load(article_id)
    storage.set_gallery(article, body.gallery)
    return view(article)


@router.patch("/{article_id}/scenes/{slug}")
def set_excluded(article_id: str, slug: str, body: ExcludeRequest) -> ArticleView:
    article = storage.load(article_id)
    storage.set_excluded(article, slug, body.excluded)
    return view(article)


@router.post("/{article_id}/generate")
def generate(
    request: Request, article_id: str, body: GenerateRequest | None = None
) -> ArticleView:
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
    return view(
        request.app.state.queue.enqueue(
            article_id, scene_slugs=scene_slugs, regenerate_listing=body.listing
        )
    )


@router.post("/{article_id}/cancel")
def cancel(request: Request, article_id: str) -> ArticleView:
    request.app.state.queue.cancel(article_id)
    return view(storage.load(article_id))


@router.post("/{article_id}/validate")
def validate(article_id: str) -> ArticleView:
    article = storage.load(article_id)
    storage.set_status(article, S.VALIDATED)
    return view(article)


@router.post("/{article_id}/unvalidate")
def unvalidate(article_id: str) -> ArticleView:
    article = storage.load(article_id)
    storage.set_status(article, S.TO_REVIEW)
    return view(article)


@router.delete("/{article_id}", status_code=204)
def delete_article(article_id: str) -> Response:
    article = storage.load(article_id)
    if article.status in (S.QUEUED, S.GENERATING):
        raise HTTPException(
            409, "Impossible de supprimer un article en cours de génération. Annule-le d'abord."
        )
    storage.delete(article.id)
    return Response(status_code=204)
