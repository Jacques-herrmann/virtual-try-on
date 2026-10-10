import os
from datetime import timedelta

import pytest

from vto.core import paths, storage
from vto.core.errors import ArticleNotFound, InvalidTransition
from vto.core.models import ArticleStatus as S
from vto.core.models import UserInput


@pytest.fixture
def photos(tmp_path, make_image):
    return [make_image(tmp_path / "src" / "front.JPG"), make_image(tmp_path / "src" / "back.png")]


def test_create_copies_photos_in_order(data_dir, photos):
    a = storage.create_article(UserInput(garment_type="robe"), photos)
    assert a.status == S.DRAFT
    assert a.photos == ["photos/001.jpg", "photos/002.png"]
    d = paths.article_dir(a.id)
    assert (d / "photos" / "001.jpg").is_file()
    assert (d / "article.json").is_file()
    assert all(p.exists() for p in photos)


def test_create_requires_at_least_one_photo(data_dir):
    with pytest.raises(ValueError):
        storage.create_article(UserInput(garment_type="robe"), [])


def test_load_round_trip(data_dir, photos):
    a = storage.create_article(UserInput(garment_type="robe", brand="Zara"), photos)
    assert storage.load(a.id) == a


def test_load_unknown_id(data_dir):
    with pytest.raises(ArticleNotFound):
        storage.load("nope")


def test_save_is_atomic(data_dir, photos, monkeypatch):
    a = storage.create_article(UserInput(garment_type="robe"), photos)
    before = (paths.article_dir(a.id) / "article.json").read_text(encoding="utf-8")

    def boom(*args, **kwargs):
        raise OSError("disque plein")

    monkeypatch.setattr(os, "replace", boom)
    a.input.brand = "Nike"
    with pytest.raises(OSError):
        storage.save(a)
    d = paths.article_dir(a.id)
    assert (d / "article.json").read_text(encoding="utf-8") == before
    assert not list(d.glob("*.tmp"))


def test_list_sorted_and_ignores_broken_dirs(data_dir, photos):
    a1 = storage.create_article(UserInput(garment_type="robe"), photos)
    a2 = storage.create_article(UserInput(garment_type="haut"), photos)
    a1.created_at = a2.created_at - timedelta(seconds=1)  # ne pas dépendre de l'horloge
    storage.save(a1)
    (paths.articles_dir() / "orphan").mkdir()
    assert [a.id for a in storage.list_articles()] == [a1.id, a2.id]


ALLOWED = [
    (S.DRAFT, S.GENERATING),
    (S.GENERATING, S.TO_REVIEW),
    (S.GENERATING, S.ERROR),
    (S.GENERATING, S.DRAFT),
    (S.TO_REVIEW, S.GENERATING),
    (S.TO_REVIEW, S.VALIDATED),
    (S.ERROR, S.GENERATING),
    (S.VALIDATED, S.TO_REVIEW),
    (S.VALIDATED, S.PUBLISHED),
]


@pytest.mark.parametrize(("from_", "to"), ALLOWED)
def test_allowed_transitions(data_dir, photos, from_, to):
    a = storage.create_article(UserInput(garment_type="robe"), photos)
    a.status = from_
    storage.set_status(a, to)
    assert storage.load(a.id).status == to


@pytest.mark.parametrize(
    ("from_", "to"), [(S.DRAFT, S.PUBLISHED), (S.PUBLISHED, S.DRAFT), (S.DRAFT, S.VALIDATED)]
)
def test_forbidden_transitions(data_dir, photos, from_, to):
    a = storage.create_article(UserInput(garment_type="robe"), photos)
    a.status = from_
    with pytest.raises(InvalidTransition):
        storage.set_status(a, to)


def test_delete_removes_folder(data_dir, photos):
    a = storage.create_article(UserInput(garment_type="robe"), photos)
    storage.delete(a.id)
    assert not paths.article_dir(a.id).exists()
