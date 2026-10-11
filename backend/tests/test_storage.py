import os
from datetime import UTC, datetime, timedelta

import pytest

from vto.core import paths, storage
from vto.core.errors import ArticleNotFound, InvalidTransition, VtoError
from vto.core.models import ArticleStatus as S
from vto.core.models import GenerationJob, Listing, SceneResult, UserInput, VintedResult


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


# --- Galerie et envoi Vinted ---


@pytest.fixture
def reviewed(data_dir, make_article, make_image):
    """Article en relecture : mannequin ok, cintre exclu, plage en erreur, pied ok."""
    article = make_article()
    d = paths.article_dir(article.id)
    for slug in ("mannequin", "cintre", "pied"):
        make_image(d / "generated" / f"{slug}.jpg")
    article.scenes = [
        SceneResult(scene="mannequin", status="ok", image="generated/mannequin.jpg"),
        SceneResult(scene="cintre", status="ok", image="generated/cintre.jpg", excluded=True),
        SceneResult(scene="plage", status="error", error="x"),
        SceneResult(scene="pied", status="ok", image="generated/pied.jpg"),
    ]
    article.status = S.TO_REVIEW
    storage.save(article)
    return article


def test_default_gallery_is_ok_scenes_without_originals(reviewed):
    assert storage.default_gallery(reviewed) == ["generated/mannequin.jpg", "generated/pied.jpg"]


def test_effective_gallery_defaults_when_unset(reviewed):
    assert storage.effective_gallery(reviewed) == storage.default_gallery(reviewed)


def test_effective_gallery_follows_custom_order(reviewed):
    order = ["photos/001.jpg", "generated/pied.jpg", "generated/mannequin.jpg"]
    storage.set_gallery(reviewed, order)
    assert storage.load(reviewed.id).gallery == order
    assert storage.effective_gallery(reviewed)[0] == "photos/001.jpg"


def test_effective_gallery_skips_images_no_longer_usable(reviewed):
    storage.set_gallery(reviewed, ["generated/pied.jpg", "generated/mannequin.jpg"])
    reviewed.scenes[0].excluded = True  # mannequin exclu après coup
    reviewed.scenes[3] = SceneResult(scene="pied", status="error", error="x")  # régénération ratée
    assert storage.effective_gallery(reviewed) == []


def test_effective_gallery_skips_missing_files(reviewed):
    storage.set_gallery(reviewed, ["generated/pied.jpg", "photos/001.jpg"])
    (paths.article_dir(reviewed.id) / "generated" / "pied.jpg").unlink()
    assert storage.effective_gallery(reviewed) == ["photos/001.jpg"]


def test_regenerated_scene_keeps_its_place(reviewed):
    storage.set_gallery(reviewed, ["generated/pied.jpg", "generated/mannequin.jpg"])
    reviewed.scenes[3] = SceneResult(scene="pied", status="ok", image="generated/pied.jpg")
    assert storage.effective_gallery(reviewed) == ["generated/pied.jpg", "generated/mannequin.jpg"]


def test_set_gallery_allowed_when_validated(reviewed):
    storage.set_status(reviewed, S.VALIDATED)
    storage.set_gallery(reviewed, ["generated/pied.jpg"])
    assert storage.load(reviewed.id).gallery == ["generated/pied.jpg"]


def test_set_gallery_none_restores_default(reviewed):
    storage.set_gallery(reviewed, ["generated/pied.jpg"])
    storage.set_gallery(reviewed, None)
    assert storage.load(reviewed.id).gallery is None


@pytest.mark.parametrize(
    "gallery",
    [
        [],
        ["generated/pied.jpg", "generated/pied.jpg"],
        ["../autre/photos/001.jpg"],
        ["generated/plage.jpg"],  # scène en erreur
        ["generated/cintre.jpg"],  # scène exclue
        ["photos/999.jpg"],
        ["article.json"],
    ],
)
def test_set_gallery_rejects_invalid(reviewed, gallery):
    with pytest.raises(VtoError) as exc:
        storage.set_gallery(reviewed, gallery)
    assert exc.value.user_message != VtoError.user_message
    assert storage.load(reviewed.id).gallery is None


def test_set_gallery_rejects_more_than_20(reviewed, make_image):
    d = paths.article_dir(reviewed.id)
    photos = [f"photos/{i:03d}.jpg" for i in range(2, 22)]
    for rel in photos:
        make_image(d / rel)
    reviewed.photos += photos
    with pytest.raises(VtoError, match="20"):
        storage.set_gallery(reviewed, ["generated/pied.jpg", *photos])


@pytest.mark.parametrize("status", [S.DRAFT, S.QUEUED, S.GENERATING, S.ERROR, S.PUBLISHED])
def test_set_gallery_refused_outside_review(reviewed, status):
    reviewed.status = status
    with pytest.raises(VtoError):
        storage.set_gallery(reviewed, ["generated/pied.jpg"])


def vinted_result(status, mode="draft"):
    return VintedResult(mode=mode, status=status, sent_at=datetime.now(UTC))


@pytest.mark.parametrize("status", ["ok", "partial"])
def test_record_vinted_success_publishes(reviewed, status):
    storage.set_status(reviewed, S.VALIDATED)
    storage.record_vinted(reviewed, vinted_result(status))
    saved = storage.load(reviewed.id)
    assert saved.status == S.PUBLISHED
    assert saved.vinted.status == status


def test_record_vinted_error_stays_validated(reviewed):
    storage.set_status(reviewed, S.VALIDATED)
    storage.record_vinted(reviewed, vinted_result("error"))
    saved = storage.load(reviewed.id)
    assert saved.status == S.VALIDATED
    assert saved.vinted.status == "error"


def test_record_vinted_requires_validated(reviewed):
    with pytest.raises(InvalidTransition):
        storage.record_vinted(reviewed, vinted_result("ok"))
    assert storage.load(reviewed.id).vinted is None


def test_nothing_leaves_published(reviewed):
    storage.set_status(reviewed, S.VALIDATED)
    storage.record_vinted(reviewed, vinted_result("partial"))
    for target in S:
        with pytest.raises(InvalidTransition):
            storage.set_status(reviewed, target)
