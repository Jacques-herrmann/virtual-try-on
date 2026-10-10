import os
from datetime import UTC, datetime, timedelta

import pytest

from vto.core import paths, storage
from vto.core.errors import ArticleNotFound, InvalidTransition, VtoError
from vto.core.models import ArticleStatus as S
from vto.core.models import GenerationJob, Listing, SceneResult, UserInput


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
    (S.DRAFT, S.QUEUED),
    (S.QUEUED, S.GENERATING),
    (S.QUEUED, S.DRAFT),
    (S.QUEUED, S.TO_REVIEW),
    (S.GENERATING, S.QUEUED),
    (S.TO_REVIEW, S.QUEUED),
    (S.ERROR, S.QUEUED),
]


@pytest.mark.parametrize(("from_", "to"), ALLOWED)
def test_allowed_transitions(data_dir, photos, from_, to):
    a = storage.create_article(UserInput(garment_type="robe"), photos)
    a.status = from_
    storage.set_status(a, to)
    assert storage.load(a.id).status == to


@pytest.mark.parametrize(
    ("from_", "to"), [
        (S.DRAFT, S.PUBLISHED),
        (S.PUBLISHED, S.DRAFT),
        (S.DRAFT, S.VALIDATED),
        (S.QUEUED, S.VALIDATED),
        (S.VALIDATED, S.QUEUED),
    ],
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


def _job(**kwargs) -> GenerationJob:
    return GenerationJob(queued_at=datetime(2026, 10, 10, tzinfo=UTC), **kwargs)


@pytest.fixture
def article(data_dir, photos):
    return storage.create_article(UserInput(garment_type="robe"), photos)


@pytest.mark.parametrize("from_", [S.DRAFT, S.TO_REVIEW, S.ERROR])
def test_enqueue(article, from_):
    article.status = from_
    storage.enqueue(article, scene_slugs=["cintre"], regenerate_listing=True)
    loaded = storage.load(article.id)
    assert loaded.status == S.QUEUED
    assert loaded.job.scene_slugs == ["cintre"] and loaded.job.regenerate_listing


def test_enqueue_sets_queued_at_now(article):
    before = datetime.now(UTC)
    storage.enqueue(article, scene_slugs=None)
    assert storage.load(article.id).job.queued_at >= before


def test_cancel_queued_without_output_goes_back_to_draft(article):
    storage.enqueue(article, scene_slugs=None)
    storage.cancel_queued(article)
    loaded = storage.load(article.id)
    assert loaded.status == S.DRAFT and loaded.job is None


def test_cancel_queued_with_output_goes_back_to_review(article):
    article.scenes = [SceneResult(scene="cintre", status="ok", image="generated/cintre.jpg")]
    article.status = S.TO_REVIEW
    storage.enqueue(article, scene_slugs=["cintre"])
    storage.cancel_queued(article)
    assert storage.load(article.id).status == S.TO_REVIEW


@pytest.mark.parametrize("status", [S.DRAFT, S.TO_REVIEW, S.ERROR, S.VALIDATED])
def test_update_input_allowed(article, status):
    article.status = status
    storage.update_input(article, UserInput(garment_type="haut", size="M"))
    assert storage.load(article.id).input.size == "M"


@pytest.mark.parametrize("status", [S.QUEUED, S.GENERATING, S.PUBLISHED])
def test_update_input_refused(article, status):
    article.status = status
    with pytest.raises(VtoError) as exc:
        storage.update_input(article, UserInput(garment_type="haut"))
    assert "modifier" in exc.value.user_message


def test_update_listing_in_review(article):
    article.status = S.TO_REVIEW
    storage.update_listing(article, Listing(title="Nouveau", description="d"))
    assert storage.load(article.id).listing.title == "Nouveau"


@pytest.mark.parametrize("status", [S.DRAFT, S.QUEUED, S.VALIDATED])
def test_update_listing_refused_outside_review(article, status):
    article.status = status
    with pytest.raises(VtoError):
        storage.update_listing(article, Listing(title="t", description="d"))


def test_set_excluded(article):
    article.status = S.TO_REVIEW
    article.scenes = [SceneResult(scene="cintre", status="ok", image="generated/cintre.jpg")]
    storage.set_excluded(article, "cintre", True)
    assert storage.load(article.id).scenes[0].excluded is True


def test_set_excluded_unknown_scene(article):
    article.status = S.TO_REVIEW
    with pytest.raises(VtoError):
        storage.set_excluded(article, "inconnue", True)


def test_set_excluded_refused_outside_review(article):
    article.scenes = [SceneResult(scene="cintre", status="ok", image="generated/cintre.jpg")]
    with pytest.raises(VtoError):
        storage.set_excluded(article, "cintre", True)


def test_recover_interrupted(data_dir, photos):
    def make(status, job=None, offset=0):
        a = storage.create_article(UserInput(garment_type="robe"), photos)
        a.status = status
        if job is not None:
            a.job = job.model_copy(update={"queued_at": job.queued_at + timedelta(seconds=offset)})
        storage.save(a)
        return a

    queued_late = make(S.QUEUED, _job(), offset=10)
    running = make(S.GENERATING, _job(scene_slugs=["cintre"]), offset=0)
    orphan = make(S.GENERATING)
    review = make(S.TO_REVIEW)

    recovered = storage.recover_interrupted()

    assert {a.id for a in recovered} == {queued_late.id, running.id, orphan.id}
    assert storage.load(running.id).status == S.QUEUED
    assert storage.load(running.id).job.scene_slugs == ["cintre"]
    orphan_job = storage.load(orphan.id).job
    assert orphan_job is not None and orphan_job.scene_slugs is None
    assert storage.load(review.id).status == S.TO_REVIEW
    times = [a.job.queued_at for a in recovered]
    assert times == sorted(times)
