"""Stockage des articles : un dossier par article, état dans article.json."""

import os
import shutil
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from vto.core import paths
from vto.core.errors import ArticleNotFound, InvalidTransition
from vto.core.models import Article, ArticleStatus, UserInput

S = ArticleStatus

TRANSITIONS: dict[ArticleStatus, set[ArticleStatus]] = {
    S.DRAFT: {S.GENERATING},
    S.GENERATING: {S.TO_REVIEW, S.ERROR, S.DRAFT},
    S.TO_REVIEW: {S.GENERATING, S.VALIDATED},
    S.ERROR: {S.GENERATING},
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


def delete(article_id: str) -> None:
    """Suppression explicite uniquement (jamais appelée implicitement par le cœur)."""
    shutil.rmtree(paths.article_dir(article_id))
