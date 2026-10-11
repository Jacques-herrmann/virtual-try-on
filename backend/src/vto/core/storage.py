"""Stockage des articles : un dossier par article, état dans article.json."""

import os
import shutil
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from vto.core import paths
from vto.core.errors import ArticleNotFound, InvalidTransition, VtoError
from vto.core.models import (
    Article,
    ArticleStatus,
    GenerationJob,
    Listing,
    UserInput,
    VintedResult,
)

S = ArticleStatus

TRANSITIONS: dict[ArticleStatus, set[ArticleStatus]] = {
    S.DRAFT: {S.QUEUED, S.GENERATING},
    S.QUEUED: {S.GENERATING, S.DRAFT, S.TO_REVIEW},
    S.GENERATING: {S.TO_REVIEW, S.ERROR, S.DRAFT, S.QUEUED},
    S.TO_REVIEW: {S.GENERATING, S.VALIDATED, S.QUEUED},
    S.ERROR: {S.GENERATING, S.QUEUED},
    S.VALIDATED: {S.TO_REVIEW, S.PUBLISHED},
    S.PUBLISHED: set(),
}

ARTICLE_FILE = "article.json"


def create_article(user_input: UserInput, photo_paths: Sequence[Path]) -> Article:
    if not photo_paths:
        raise ValueError("Un article a besoin d'au moins une photo.")
    article = Article(
        id=uuid.uuid4().hex,
        created_at=datetime.now(UTC),
        input=user_input,
    )
    photos_dir = paths.article_dir(article.id) / "photos"
    photos_dir.mkdir(parents=True)
    for i, src in enumerate(photo_paths, start=1):
        name = f"{i:03d}{Path(src).suffix.lower()}"
        shutil.copy2(src, photos_dir / name)
        article.photos.append(f"photos/{name}")
    save(article)
    return article


def load(article_id: str) -> Article:
    file = paths.article_dir(article_id) / ARTICLE_FILE
    if not file.is_file():
        raise ArticleNotFound(article_id)
    return Article.model_validate_json(file.read_text(encoding="utf-8"))


def save(article: Article) -> None:
    file = paths.article_dir(article.id) / ARTICLE_FILE
    tmp = file.with_suffix(".json.tmp")
    tmp.write_text(article.model_dump_json(indent=2), encoding="utf-8")
    try:
        os.replace(tmp, file)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def list_articles() -> list[Article]:
    articles = [
        load(d.name)
        for d in paths.articles_dir().iterdir()
        if (d / ARTICLE_FILE).is_file()
    ]
    return sorted(articles, key=lambda a: a.created_at)


def set_status(article: Article, new: ArticleStatus) -> None:
    if new not in TRANSITIONS[article.status]:
        raise InvalidTransition(article.status.value, new.value)
    article.status = new
    save(article)


def has_output(article: Article) -> bool:
    return article.listing is not None or any(s.status == "ok" for s in article.scenes)


def enqueue(
    article: Article,
    *,
    scene_slugs: Sequence[str] | None = None,
    regenerate_listing: bool = False,
) -> None:
    """Place l'article en file ; la demande est persistée pour survivre à un redémarrage."""
    if S.QUEUED not in TRANSITIONS[article.status]:
        raise InvalidTransition(article.status.value, S.QUEUED.value)
    article.job = GenerationJob(
        scene_slugs=list(scene_slugs) if scene_slugs is not None else None,
        regenerate_listing=regenerate_listing,
        queued_at=datetime.now(UTC),
    )
    set_status(article, S.QUEUED)


def cancel_queued(article: Article) -> None:
    """Annule une demande pas encore démarrée."""
    article.job = None
    set_status(article, S.TO_REVIEW if has_output(article) else S.DRAFT)


EDITABLE_INPUT = {S.DRAFT, S.TO_REVIEW, S.ERROR, S.VALIDATED}


def update_input(article: Article, user_input: UserInput) -> None:
    if article.status not in EDITABLE_INPUT:
        raise VtoError("Impossible de modifier la saisie pendant la génération ou après l'envoi.")
    article.input = user_input
    save(article)


def _require_review(article: Article) -> None:
    if article.status != S.TO_REVIEW:
        raise VtoError("Cette modification n'est possible que pendant la relecture.")


def update_listing(article: Article, listing: Listing) -> None:
    _require_review(article)
    article.listing = listing
    save(article)


def set_excluded(article: Article, scene_slug: str, excluded: bool) -> None:
    _require_review(article)
    for result in article.scenes:
        if result.scene == scene_slug:
            result.excluded = excluded
            save(article)
            return
    raise VtoError(f"Aucune image pour la scène « {scene_slug} ».")


MAX_GALLERY = 20


def default_gallery(article: Article) -> list[str]:
    """Images des scènes réussies non exclues, dans l'ordre des scènes."""
    return [r.image for r in article.scenes if r.status == "ok" and r.image and not r.excluded]


def _usable_images(article: Article) -> list[str]:
    return default_gallery(article) + article.photos


def effective_gallery(article: Article) -> list[str]:
    """Images à envoyer sur Vinted : la galerie choisie, sans les images devenues inutilisables."""
    usable = set(_usable_images(article))
    article_dir = paths.article_dir(article.id)
    chosen = default_gallery(article) if article.gallery is None else article.gallery
    return [p for p in chosen if p in usable and (article_dir / p).is_file()][:MAX_GALLERY]


def set_gallery(article: Article, gallery: Sequence[str] | None) -> None:
    """Ordre des photos pour Vinted ; `None` revient à l'ordre par défaut."""
    if article.status not in (S.TO_REVIEW, S.VALIDATED):
        raise VtoError("Les photos ne peuvent être réordonnées qu'avant l'envoi sur Vinted.")
    if gallery is not None:
        if not gallery:
            raise VtoError("Choisis au moins une photo à envoyer sur Vinted.")
        if len(gallery) > MAX_GALLERY:
            raise VtoError(f"Vinted accepte au plus {MAX_GALLERY} photos par annonce.")
        if len(set(gallery)) != len(gallery):
            raise VtoError("Une même photo apparaît deux fois.")
        if not set(gallery) <= set(_usable_images(article)):
            raise VtoError("Certaines photos ne font pas partie de cet article.")
        gallery = list(gallery)
    article.gallery = gallery
    save(article)


def record_vinted(article: Article, result: VintedResult) -> None:
    """Enregistre un envoi : réussi ou partiel → PUBLISHED ; en échec, reste VALIDATED."""
    if article.status != S.VALIDATED:
        raise InvalidTransition(article.status.value, S.PUBLISHED.value)
    article.vinted = result
    if result.status == "error":
        save(article)
    else:
        set_status(article, S.PUBLISHED)


def recover_interrupted() -> list[Article]:
    """Remet en file les articles interrompus et renvoie la file, dans l'ordre d'arrivée."""
    queued = []
    for article in list_articles():
        if article.status == S.GENERATING:
            if article.job is None:
                article.job = GenerationJob(queued_at=datetime.now(UTC))
            set_status(article, S.QUEUED)
        if article.status == S.QUEUED:
            if article.job is None:
                article.job = GenerationJob(queued_at=datetime.now(UTC))
                save(article)
            queued.append(article)
    return sorted(queued, key=lambda a: a.job.queued_at)


def delete(article_id: str) -> None:
    """Suppression explicite uniquement (jamais appelée implicitement par le cœur)."""
    shutil.rmtree(paths.article_dir(article_id))
