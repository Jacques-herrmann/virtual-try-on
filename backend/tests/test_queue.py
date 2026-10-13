import threading

import pytest

from fakes import FakeClient
from vto.api.queue import GenerationQueue
from vto.core import config, errors, storage
from vto.core.models import ArticleStatus as S

TIMEOUT = 5


class Recorder:
    """Fonction de traitement injectée : note les appels, peut bloquer ou lever."""

    def __init__(self):
        self.calls = []
        self.cancels = {}
        self.block = {}  # article_id -> Event à attendre
        self.started = {}  # article_id -> Event signalé au démarrage
        self.raise_for = {}

    def gate(self, article_id):
        self.block[article_id] = threading.Event()
        self.started[article_id] = threading.Event()
        return self.started[article_id], self.block[article_id]

    def __call__(self, article_id, *, client, settings, cancel):
        self.calls.append((article_id, client))
        self.cancels[article_id] = cancel
        if article_id in self.started:
            self.started[article_id].set()
            assert self.block[article_id].wait(TIMEOUT)
        if article_id in self.raise_for:
            raise self.raise_for[article_id]
        article = storage.load(article_id)
        storage.set_status(article, S.GENERATING)
        article.job = None
        storage.set_status(article, S.TO_REVIEW)


@pytest.fixture
def keyed(data_dir):
    config.save_settings(config.Settings(gemini_api_key="k"))


@pytest.fixture
def make_queue(keyed):
    queues = []

    def _make(recorder, factory=None):
        q = GenerationQueue(factory or (lambda key: FakeClient()), process=recorder)
        queues.append(q)
        return q

    yield _make
    for q in queues:
        q.stop()


def ids(*articles):
    return [a.id for a in articles]


def test_fifo(make_queue, make_article):
    rec = Recorder()
    q = make_queue(rec)
    a, b, c = make_article(), make_article(), make_article()
    q.start()
    for art in (a, b, c):
        q.enqueue(art.id)
    assert q.wait_idle(TIMEOUT)
    assert [call[0] for call in rec.calls] == ids(a, b, c)
    assert all(storage.load(x.id).status == S.TO_REVIEW for x in (a, b, c))


def test_enqueue_persists_job(make_queue, make_article):
    rec = Recorder()
    q = make_queue(rec)  # pas démarrée
    a = make_article()
    q.enqueue(a.id, scene_slugs=["cintre"], regenerate_listing=True)
    loaded = storage.load(a.id)
    assert loaded.status == S.QUEUED
    assert loaded.job.scene_slugs == ["cintre"] and loaded.job.regenerate_listing
    assert q.status()["pending"] == [a.id]


def test_status_shows_running_and_pending(make_queue, make_article):
    rec = Recorder()
    q = make_queue(rec)
    a, b = make_article(), make_article()
    started, release = rec.gate(a.id)
    q.start()
    q.enqueue(a.id)
    q.enqueue(b.id)
    assert started.wait(TIMEOUT)
    status = q.status()
    assert status["running"] == a.id and status["pending"] == [b.id]
    assert status["paused"] is False and status["reason"] is None
    release.set()
    assert q.wait_idle(TIMEOUT)
    assert q.status()["running"] is None


def test_start_recovers_from_disk(make_queue, make_article):
    a, b = make_article(), make_article()
    storage.enqueue(storage.load(a.id))
    interrupted = storage.load(b.id)
    storage.enqueue(interrupted)
    storage.set_status(interrupted, S.GENERATING)
    rec = Recorder()
    q = make_queue(rec)
    q.start()
    assert q.wait_idle(TIMEOUT)
    assert [call[0] for call in rec.calls] == ids(a, b)


def test_cancel_pending(make_queue, make_article):
    rec = Recorder()
    q = make_queue(rec)
    a = make_article()
    q.enqueue(a.id)
    q.cancel(a.id)
    assert q.status()["pending"] == []
    assert storage.load(a.id).status == S.DRAFT
    q.start()
    assert q.wait_idle(TIMEOUT)
    assert rec.calls == []


def test_cancel_running_sets_event(make_queue, make_article):
    rec = Recorder()
    q = make_queue(rec)
    a = make_article()
    started, release = rec.gate(a.id)
    q.start()
    q.enqueue(a.id)
    assert started.wait(TIMEOUT)
    q.cancel(a.id)
    assert rec.cancels[a.id].is_set()
    release.set()
    assert q.wait_idle(TIMEOUT)


def test_cancel_unknown_article(make_queue, make_article):
    q = make_queue(Recorder())
    with pytest.raises(errors.VtoError):
        q.cancel(make_article().id)


def test_fatal_error_pauses_then_resume(make_queue, make_article):
    rec = Recorder()
    q = make_queue(rec)
    a, b = make_article(), make_article()
    rec.raise_for[a.id] = errors.InvalidApiKey()
    q.start()
    q.enqueue(a.id)
    q.enqueue(b.id)
    assert q.wait_idle(TIMEOUT)
    status = q.status()
    assert status["paused"] is True
    assert status["reason"] == errors.InvalidApiKey.user_message
    assert status["pending"] == [b.id]
    assert [call[0] for call in rec.calls] == [a.id]
    q.resume()
    assert q.wait_idle(TIMEOUT)
    assert [call[0] for call in rec.calls] == ids(a, b)
    assert q.status()["paused"] is False


def test_enqueue_refused_without_license(keyed, make_article):
    from vto.licensing import LicenseError

    q = GenerationQueue(lambda key: FakeClient(), process=Recorder(), licensed=lambda: False)
    a = make_article()
    with pytest.raises(LicenseError) as exc:
        q.enqueue(a.id)
    assert exc.value.user_message == "Cette action demande un abonnement actif."
    with pytest.raises(LicenseError):
        q.enqueue(a.id, scene_slugs=["cintre"], regenerate_listing=True)
    assert storage.load(a.id).status != S.QUEUED
    assert q.status()["pending"] == []


def test_license_ended_while_waiting_pauses_without_losing_article(make_queue, make_article):
    licensed = [True]
    rec = Recorder()
    q = GenerationQueue(lambda key: FakeClient(), process=rec, licensed=lambda: licensed[0])
    a = make_article()
    q.enqueue(a.id)
    licensed[0] = False
    q.start()
    try:
        assert q.wait_idle(TIMEOUT)
        status = q.status()
        assert status["paused"] is True
        assert status["reason"] == "Cette action demande un abonnement actif."
        assert status["pending"] == [a.id]
        assert rec.calls == []
        licensed[0] = True
        q.resume()
        assert q.wait_idle(TIMEOUT)
        assert [call[0] for call in rec.calls] == [a.id]
    finally:
        q.stop()


def test_missing_key_pauses_without_losing_article(make_queue, make_article):
    config.save_settings(config.Settings())
    rec = Recorder()
    q = make_queue(rec)
    a = make_article()
    q.start()
    q.enqueue(a.id)
    assert q.wait_idle(TIMEOUT)
    assert q.status()["paused"] is True
    assert q.status()["pending"] == [a.id]
    assert storage.load(a.id).status == S.QUEUED
    config.save_settings(config.Settings(gemini_api_key="k"))
    q.resume()
    assert q.wait_idle(TIMEOUT)
    assert [call[0] for call in rec.calls] == [a.id]


def test_client_built_per_article_with_current_key(make_queue, make_article):
    keys = []
    rec = Recorder()
    q = make_queue(rec, factory=lambda key: keys.append(key) or FakeClient())
    a, b = make_article(), make_article()
    started, release = rec.gate(a.id)
    q.start()
    q.enqueue(a.id)
    q.enqueue(b.id)
    assert started.wait(TIMEOUT)
    config.save_settings(config.Settings(gemini_api_key="nouvelle"))
    release.set()
    assert q.wait_idle(TIMEOUT)
    assert keys == ["k", "nouvelle"]


def test_unexpected_error_does_not_stop_queue(make_queue, make_article, caplog):
    rec = Recorder()
    q = make_queue(rec)
    a, b = make_article(), make_article()
    rec.raise_for[a.id] = RuntimeError("boom")
    q.start()
    q.enqueue(a.id)
    q.enqueue(b.id)
    assert q.wait_idle(TIMEOUT)
    assert [call[0] for call in rec.calls] == ids(a, b)
    assert "boom" in caplog.text
    assert q.status()["paused"] is False


def test_stop_prevents_further_work(make_queue, make_article):
    rec = Recorder()
    q = make_queue(rec)
    a = make_article()
    q.start()
    q.stop()
    q.enqueue(a.id)
    assert q.wait_idle(TIMEOUT)
    assert rec.calls == []


def test_is_busy_while_running_or_pending(make_queue, make_article):
    rec = Recorder()
    q = make_queue(rec)
    assert q.is_busy() is False
    a = make_article()
    q.enqueue(a.id)  # pas démarrée : en attente
    assert q.is_busy() is True
    started, release = rec.gate(a.id)
    q.start()
    assert started.wait(TIMEOUT)
    assert q.is_busy() is True
    release.set()
    assert q.wait_idle(TIMEOUT)
    assert q.is_busy() is False


def test_paused_queue_is_not_busy(make_queue, make_article):
    # En pause, rien ne tourne ; les articles en attente reprennent au prochain lancement.
    config.save_settings(config.Settings())
    q = make_queue(Recorder())
    q.start()
    q.enqueue(make_article().id)
    assert q.wait_idle(TIMEOUT)
    assert q.is_busy() is False
    config.save_settings(config.Settings(gemini_api_key="k"))
