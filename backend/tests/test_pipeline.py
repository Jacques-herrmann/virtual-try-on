import threading
from collections import deque

import pytest

from fakes import FakeClient
from vto.core import errors, pipeline, storage
from vto.core.config import Settings
from vto.core.models import ArticleStatus as S
from vto.core.models import Listing

LISTING = Listing(title="t", description="d")


@pytest.fixture
def two_scenes(data_dir, make_scene):
    make_scene("mannequin", order=1)
    make_scene("cintre", order=2)


def run(article, client, **kw):
    return pipeline.process_article(article.id, client=client, settings=Settings(), **kw)


def listing_client(**kw):
    return FakeClient(json_responses=deque([LISTING]), **kw)


def test_nominal(two_scenes, make_article):
    article = make_article()
    progress = []
    done = run(article, listing_client(), on_progress=lambda *a: progress.append(a[1]))
    assert done.status == S.TO_REVIEW
    assert [(s.scene, s.status) for s in done.scenes] == [("mannequin", "ok"), ("cintre", "ok")]
    assert done.listing == LISTING
    assert progress == ["scene", "scene", "listing", "done"]
    assert storage.load(article.id) == done


def test_one_scene_failing_keeps_the_other(two_scenes, make_article):
    client = listing_client(image_responses=deque([errors.NoImageReturned()]))
    done = run(make_article(), client)
    assert done.status == S.TO_REVIEW
    assert done.scenes[0].status == "error"
    assert done.scenes[0].error == errors.NoImageReturned.user_message
    assert done.scenes[1].status == "ok"


def test_all_scenes_failing_is_error(two_scenes, make_article):
    client = listing_client(image_responses=deque([errors.ModelUnavailable()] * 2))
    done = run(make_article(), client)
    assert done.status == S.ERROR
    assert done.error


def test_listing_failure_is_error(two_scenes, make_article):
    client = FakeClient(json_responses=deque([errors.InvalidModelOutput()]))
    done = run(make_article(), client)
    assert done.status == S.ERROR
    assert done.error == errors.InvalidModelOutput.user_message


def test_unexpected_exception_does_not_crash_article(two_scenes, make_article):
    client = listing_client(image_responses=deque([RuntimeError("boom")]))
    done = run(make_article(), client)
    assert done.scenes[0].status == "error"
    assert done.status == S.TO_REVIEW


def test_invalid_key_stops_batch(two_scenes, make_article):
    a1, a2 = make_article(), make_article()
    client = FakeClient(image_responses=deque([errors.InvalidApiKey()]))
    with pytest.raises(errors.InvalidApiKey):
        pipeline.process_batch([a1.id, a2.id], client=client, settings=Settings())
    assert storage.load(a1.id).status == S.ERROR
    assert storage.load(a2.id).status == S.DRAFT


def test_cancel_before_first_scene_returns_to_draft(two_scenes, make_article):
    cancel = threading.Event()
    cancel.set()
    done = run(make_article(), listing_client(), cancel=cancel)
    assert done.status == S.DRAFT


def test_cancel_after_a_scene_goes_to_review(two_scenes, make_article):
    cancel = threading.Event()

    def on_progress(article_id, step, detail):
        cancel.set()

    done = run(make_article(), listing_client(), cancel=cancel, on_progress=on_progress)
    assert done.status == S.TO_REVIEW
    assert [s.status for s in done.scenes] == ["ok", "pending"]


def test_regenerate_single_scene(two_scenes, make_article):
    article = make_article()
    run(article, listing_client())
    client = FakeClient()
    done = run(article, client, scene_slugs=["cintre"])
    assert [c.kind for c in client.calls] == ["image"]
    assert done.status == S.TO_REVIEW and done.listing == LISTING


def test_regenerate_listing_only(two_scenes, make_article):
    article = make_article()
    run(article, listing_client())
    new = Listing(title="nouveau", description="d")
    client = FakeClient(json_responses=deque([new]))
    done = pipeline.regenerate_listing(article.id, client=client, settings=Settings())
    assert [c.kind for c in client.calls] == ["json"]
    assert done.listing.title == "nouveau"


def test_unknown_scene_is_rejected(two_scenes, make_article):
    article = make_article()
    with pytest.raises(errors.VtoError, match="inconnue"):
        run(article, FakeClient(), scene_slugs=["plage"])
    assert storage.load(article.id).status == S.DRAFT


def test_build_client_requires_key(data_dir):
    with pytest.raises(errors.MissingApiKey):
        pipeline.build_client(Settings())


def queued(article, **job):
    article = storage.load(article.id)
    storage.enqueue(article, **job)
    return article


def test_queued_full_run_clears_job(two_scenes, make_article):
    article = queued(make_article())
    done = run(article, listing_client())
    assert done.status == S.TO_REVIEW and done.job is None
    assert storage.load(article.id).job is None


def test_queued_job_drives_scenes(two_scenes, make_article):
    article = make_article()
    run(article, listing_client())
    queued(article, scene_slugs=["cintre"])
    client = FakeClient()
    done = run(article, client)
    assert [c.kind for c in client.calls] == ["image"]
    assert done.status == S.TO_REVIEW


def test_queued_job_listing_only(two_scenes, make_article):
    article = make_article()
    run(article, listing_client())
    queued(article, scene_slugs=[], regenerate_listing=True)
    client = FakeClient(json_responses=deque([Listing(title="nouveau", description="d")]))
    done = run(article, client)
    assert [c.kind for c in client.calls] == ["json"]
    assert done.listing.title == "nouveau"


def test_queued_job_drops_deleted_scene(two_scenes, make_article):
    article = make_article()
    run(article, listing_client())
    queued(article, scene_slugs=["plage", "cintre"])
    client = FakeClient()
    done = run(article, client)
    assert [c.kind for c in client.calls] == ["image"]
    assert done.status == S.TO_REVIEW and done.job is None


def test_job_kept_during_processing(two_scenes, make_article):
    article = queued(make_article())
    seen = []

    def on_progress(article_id, step, detail):
        seen.append(storage.load(article_id).job is not None)

    run(article, listing_client(), on_progress=on_progress)
    assert seen == [True, True, True, True]


def test_job_cleared_on_error(two_scenes, make_article):
    article = queued(make_article())
    client = FakeClient(json_responses=deque([errors.InvalidModelOutput()]))
    done = run(article, client)
    assert done.status == S.ERROR
    assert storage.load(article.id).job is None


def test_job_cleared_on_cancel(two_scenes, make_article):
    article = queued(make_article())
    cancel = threading.Event()
    cancel.set()
    done = run(article, listing_client(), cancel=cancel)
    assert done.status == S.DRAFT
    assert storage.load(article.id).job is None


def test_job_cleared_on_fatal_error(two_scenes, make_article):
    article = queued(make_article())
    with pytest.raises(errors.InvalidApiKey):
        run(article, FakeClient(image_responses=deque([errors.InvalidApiKey()])))
    loaded = storage.load(article.id)
    assert loaded.status == S.ERROR and loaded.job is None


def test_regenerated_scene_is_no_longer_excluded(two_scenes, make_article):
    article = make_article()
    run(article, listing_client())
    article = storage.load(article.id)
    storage.set_excluded(article, "mannequin", True)
    storage.set_excluded(article, "cintre", True)
    queued(article, scene_slugs=["cintre"])
    done = run(article, FakeClient())
    assert {s.scene: s.excluded for s in done.scenes} == {"mannequin": True, "cintre": False}
