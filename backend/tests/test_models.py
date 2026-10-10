from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from vto.core.models import (
    Article,
    ArticleStatus,
    GenerationJob,
    Listing,
    SceneResult,
    UserInput,
)


def make_article() -> Article:
    return Article(
        id="abc",
        created_at=datetime(2026, 10, 10, tzinfo=UTC),
        status=ArticleStatus.TO_REVIEW,
        input=UserInput(garment_type="robe", brand="Zara", notes="petite tache"),
        photos=["photos/001.jpg"],
        scenes=[SceneResult(scene="mannequin", status="ok", image="generated/mannequin.jpg")],
        listing=Listing(
            title="Zara robe longue M bleu",
            description="Jolie robe",
            condition="Très bon état",
            price=12.5,
            parcel_size="Petit",
        ),
    )


def test_article_json_round_trip():
    article = make_article()
    assert Article.model_validate_json(article.model_dump_json()) == article


def test_status_serialized_as_string():
    assert '"status":"to_review"' in make_article().model_dump_json()


def test_user_input_only_requires_garment_type():
    ui = UserInput(garment_type="haut")
    assert ui.brand is None and ui.price is None


def test_user_input_rejects_unknown_garment_type():
    with pytest.raises(ValidationError):
        UserInput(garment_type="chapeau")


def test_listing_rejects_unknown_condition():
    with pytest.raises(ValidationError):
        Listing(title="t", description="d", condition="Comme neuf ou presque")


def test_listing_unknown_fields_default_to_none():
    listing = Listing(title="t", description="d")
    assert listing.brand is None and listing.condition is None


def test_queued_status_value():
    assert ArticleStatus.QUEUED == "queued"


def test_article_with_job_and_excluded_round_trip():
    article = make_article()
    article.job = GenerationJob(
        scene_slugs=["cintre"],
        regenerate_listing=True,
        queued_at=datetime(2026, 10, 10, tzinfo=UTC),
    )
    article.scenes[0].excluded = True
    assert Article.model_validate_json(article.model_dump_json()) == article


def test_old_article_json_loads_with_defaults():
    data = make_article().model_dump(mode="json")
    del data["job"]
    del data["scenes"][0]["excluded"]
    article = Article.model_validate(data)
    assert article.job is None
    assert article.scenes[0].excluded is False


def test_job_defaults_to_full_run():
    job = GenerationJob(queued_at=datetime(2026, 10, 10, tzinfo=UTC))
    assert job.scene_slugs is None and job.regenerate_listing is False
