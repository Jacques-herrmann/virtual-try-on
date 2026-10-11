import threading

import pytest
from playwright.sync_api import Error as PlaywrightError

from samples import minimal
from vto.core import config, paths, storage
from vto.core.models import ArticleStatus as S
from vto.vinted import browser, remote
from vto.vinted.filler import FillReport
from vto.vinted.schema import VintedData
from vto.vinted.worker import (
    LOGIN_TIMEOUT_MESSAGE,
    UNEXPECTED_MESSAGE,
    Busy,
    VintedWorker,
)

TIMEOUT = 5
CLOSED = "Target page, context or browser has been closed"


class Threads:
    """Note le thread de chaque appel au navigateur."""

    def __init__(self):
        self.names = set()

    def note(self):
        self.names.add(threading.current_thread().name)


class FakePage:
    def __init__(self, threads):
        self.threads = threads
        self.url = "about:blank"
        self.visited = []

    def goto(self, url):
        self.threads.note()
        self.visited.append(url)
        self.url = url


class FakeContext:
    def __init__(self, threads):
        self.threads = threads
        self.pages = [FakePage(threads)]
        self.closed = False

    def new_page(self):
        self.threads.note()
        page = FakePage(self.threads)
        self.pages.append(page)
        return page

    def close(self):
        self.threads.note()
        self.closed = True


class FakePlaywright:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class FakeFiller:
    """Remplissage factice : rapport par article, blocage ou exception à la demande."""

    def __init__(self, threads):
        self.threads = threads
        self.calls = []
        self.reports = {}
        self.raise_for = {}
        self.started = {}
        self.release = {}

    def gate(self, article_id):
        self.started[article_id] = threading.Event()
        self.release[article_id] = threading.Event()
        return self.started[article_id], self.release[article_id]

    def __call__(self, page, article, data, catalog, mode):
        self.threads.note()
        self.calls.append((article.id, mode))
        if article.id in self.started:
            self.started[article.id].set()
            assert self.release[article.id].wait(TIMEOUT)
        if article.id in self.raise_for:
            raise self.raise_for[article.id]
        return self.reports.get(
            article.id,
            FillReport(mode=mode, status="ok", url=f"https://www.vinted.fr/items/{article.id}"),
        )


class Login:
    """État de connexion scriptable ; `answers` est consommé avant `default`."""

    def __init__(self, threads, default=True):
        self.threads = threads
        self.default = default
        self.answers = []
        self.calls = 0
        self.on_call = lambda: None

    def __call__(self, page, data):
        self.threads.note()
        self.calls += 1
        self.on_call()
        return self.answers.pop(0) if self.answers else self.default


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        self.now += 1
        return self.now


@pytest.fixture
def env(data_dir):
    threads = Threads()
    env = type("Env", (), {})()
    env.threads = threads
    env.contexts = []
    env.filler = FakeFiller(threads)
    env.login = Login(threads)
    env.playwright = FakePlaywright()
    env.open_error = None
    env.loads = 0

    def open_context(pw):
        threads.note()
        if env.open_error is not None:
            raise env.open_error
        ctx = FakeContext(threads)
        env.contexts.append(ctx)
        return ctx

    def load_data():
        env.loads += 1
        return remote.LoadedData(VintedData.model_validate(minimal()), "bundled", "r1")

    workers = []

    def make(**kw):
        params = dict(
            start_playwright=lambda: env.playwright,
            open_context=open_context,
            is_logged_in=env.login,
            fill=env.filler,
            load_data=load_data,
            clock=Clock(),
            login_timeout=5,
            login_poll=0,
            pause_range=(0, 0),
        )
        params.update(kw)
        worker = VintedWorker(**params)
        worker.start()
        workers.append(worker)
        return worker

    env.make = make
    yield env
    for worker in workers:
        worker.shutdown(TIMEOUT)


@pytest.fixture
def validated(make_article):
    def _make(n):
        ids = []
        for _ in range(n):
            article = make_article()
            article.status = S.VALIDATED
            storage.save(article)
            ids.append(article.id)
        return ids

    return _make


def run(worker, ids):
    worker.send(ids)
    assert worker.wait_idle(TIMEOUT)
    return worker.status()


def test_send_batch(env, validated):
    ids = validated(3)
    status = run(env.make(), ids)
    assert [c[0] for c in env.filler.calls] == ids
    for article_id in ids:
        article = storage.load(article_id)
        assert article.status == S.PUBLISHED
        assert article.vinted.status == "ok"
        assert article.vinted.mode == "draft"
        assert article.vinted.url.endswith(article_id)
    assert status["batch"] == {
        "running": False, "paused_reason": None, "current": None,
        "done": 3, "total": 3, "failed": 0, "message": None,
    }
    assert status["data_revision"] == "r1" and status["data_source"] == "bundled"
    assert env.contexts[-1].closed


def test_publish_mode_from_settings(env, validated):
    config.save_settings(config.Settings(vinted_mode="publish"))
    run(env.make(), validated(1))
    assert env.filler.calls[0][1] == "publish"


def test_partial_and_error_reports(env, validated):
    ok, partial, failed = validated(3)
    env.filler.reports[partial] = FillReport(
        mode="draft", status="partial", missing_fields=["Marque"], url="u"
    )
    env.filler.reports[failed] = FillReport(
        mode="draft", status="error", error="Vinted ne répond pas."
    )
    status = run(env.make(), [ok, partial, failed])
    assert storage.load(partial).status == S.PUBLISHED
    assert storage.load(partial).vinted.missing_fields == ["Marque"]
    article = storage.load(failed)
    assert article.status == S.VALIDATED  # « Réessayer » reste possible
    assert article.vinted.error == "Vinted ne répond pas."
    assert (status["batch"]["done"], status["batch"]["failed"]) == (3, 1)


def test_article_no_longer_validated_is_skipped(env, validated):
    first, second = validated(2)
    article = storage.load(second)
    storage.set_status(article, S.TO_REVIEW)
    status = run(env.make(), [first, second])
    assert [c[0] for c in env.filler.calls] == [first]
    assert storage.load(second).vinted is None
    assert status["batch"]["done"] == 2


def test_stop_finishes_current_article(env, validated):
    ids = validated(3)
    started, release = env.filler.gate(ids[1])
    worker = env.make()
    worker.send(ids)
    assert started.wait(TIMEOUT)
    assert worker.status()["batch"]["current"] == ids[1]
    worker.stop()
    release.set()
    assert worker.wait_idle(TIMEOUT)
    assert storage.load(ids[1]).status == S.PUBLISHED
    third = storage.load(ids[2])
    assert third.status == S.VALIDATED and third.vinted is None
    assert worker.status()["batch"]["done"] == 2


def test_login_pause_then_resume(env, validated):
    env.login.answers = [False, False, False]
    ids = validated(1)
    worker = env.make()
    statuses = []
    env.login.on_call = lambda: statuses.append(worker.status()["batch"]["paused_reason"])
    status = run(worker, ids)
    assert "login_required" in statuses
    assert status["batch"]["paused_reason"] is None
    assert storage.load(ids[0]).status == S.PUBLISHED
    assert status["connected"] is True


def test_login_timeout_ends_batch(env, validated):
    env.login.default = False
    ids = validated(2)
    status = run(env.make(login_timeout=10), ids)
    assert status["batch"]["message"] == LOGIN_TIMEOUT_MESSAGE
    assert env.filler.calls == []
    assert all(storage.load(i).status == S.VALIDATED for i in ids)
    assert status["connected"] is False


def test_window_closed_during_article(env, validated):
    ids = validated(3)
    env.filler.raise_for[ids[1]] = PlaywrightError(f"Page.click: {CLOSED}")
    status = run(env.make(), ids)
    second = storage.load(ids[1])
    assert second.status == S.VALIDATED and second.vinted.status == "error"
    third = storage.load(ids[2])
    assert third.status == S.VALIDATED and third.vinted is None
    assert status["batch"]["message"] == (
        "La fenêtre Vinted a été fermée. 2 article(s) n'ont pas été envoyés."
    )
    assert status["batch"]["failed"] == 1


def test_unexpected_exception_does_not_kill_thread(env, validated, caplog):
    first, second = validated(2)
    env.filler.raise_for[first] = RuntimeError("bogue")
    worker = env.make()
    status = run(worker, [first, second])
    assert storage.load(first).vinted.error == UNEXPECTED_MESSAGE
    assert storage.load(second).status == S.PUBLISHED
    assert "bogue" in caplog.text
    # Le thread répond toujours.
    third = validated(1)
    assert run(worker, third)["batch"]["done"] == 1
    assert status["batch"]["failed"] == 1


def test_browser_errors_end_batch_with_message(env, validated):
    env.open_error = browser.BrowserMissing()
    ids = validated(1)
    status = run(env.make(), ids)
    assert status["batch"]["message"] == browser.BrowserMissing.user_message
    assert storage.load(ids[0]).vinted is None


def test_second_send_is_refused(env, validated):
    ids = validated(2)
    started, release = env.filler.gate(ids[0])
    worker = env.make()
    worker.send(ids[:1])
    assert started.wait(TIMEOUT)
    with pytest.raises(Busy):
        worker.send(ids[1:])
    with pytest.raises(Busy):
        worker.connect()
    release.set()
    assert worker.wait_idle(TIMEOUT)


def test_connect_checks_then_closes(env):
    env.login.answers = [False, False]
    worker = env.make()
    worker.connect()
    assert worker.status()["connecting"] is True
    assert worker.wait_idle(TIMEOUT)
    status = worker.status()
    assert status["connected"] is True and status["connecting"] is False
    assert env.login.calls == 3
    assert env.contexts[-1].closed


def test_connect_timeout(env):
    env.login.default = False
    worker = env.make()
    worker.connect()
    assert worker.wait_idle(TIMEOUT)
    assert worker.status()["connected"] is False
    assert env.contexts[-1].closed


def test_disconnect_removes_only_the_profile(env, validated, data_dir):
    validated(1)
    profile = paths.browser_profile_dir()
    (profile / "Default").mkdir()
    (profile / "Default" / "Cookies").write_text("x")
    worker = env.make()
    worker.disconnect()
    assert worker.wait_idle(TIMEOUT)
    assert not profile.exists()
    assert worker.status()["connected"] is False
    assert paths.articles_dir().is_dir() and any(paths.articles_dir().iterdir())
    assert paths.settings_file().parent == data_dir


def test_open_url(env):
    worker = env.make()
    worker.open_url("https://www.vinted.fr/items/42")
    assert worker.wait_idle(TIMEOUT)
    page = env.contexts[-1].pages[0]
    assert page.visited == ["https://www.vinted.fr/items/42"]
    assert not env.contexts[-1].closed  # la fenêtre reste au vendeur


def test_data_loaded_in_background_at_start(env):
    worker = env.make()
    assert worker.wait_idle(TIMEOUT)
    for _ in range(100):
        if worker.loaded is not None:
            break
        threading.Event().wait(0.01)
    assert worker.loaded.revision == "r1"


def test_browser_used_only_from_worker_thread(env, validated):
    worker = env.make()
    run(worker, validated(2))
    worker.connect()
    assert worker.wait_idle(TIMEOUT)
    worker.shutdown(TIMEOUT)
    assert env.threads.names == {"vinted-worker"}
    assert env.playwright.stopped
