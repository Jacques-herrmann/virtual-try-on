"""L'application complète pour le tournage : vrai front, vraie API, Gemini rejoué, Vinted simulé.

Tout se passe dans un dossier de données temporaire ; aucun réseau, aucun compte.
"""

import os
import secrets
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import uvicorn

from vto.api import app as api_app
from vto.api.queue import GenerationQueue
from vto.core import config, scenes
from vto.desktop import _wait_until_ready, find_free_port, login_url
from vto.licensing.state import LicenseManager
from vto.tools.tutorial.replay import ReplayClient
from vto.vinted import filler, remote
from vto.vinted.schema import VintedData
from vto.vinted.worker import VintedWorker

# Visites de frontend/src/tours.ts : toutes marquées vues, aucune bulle dans le film.
TOURS = ("articles", "articles-list", "article-form", "review", "scenes", "settings")
DRAFT_URL = "https://www.vinted.fr/items/new"


class MissingFront(Exception):
    pass


class _FakeContext:
    """Fenêtre Vinted simulée : une page vide, jamais affichée."""

    def __init__(self):
        self.pages = [object()]

    def new_page(self):
        return self.pages[0]

    def close(self):
        pass


class _FakePlaywright:
    def stop(self):
        pass


def _bundled_data() -> remote.LoadedData:
    data = VintedData.model_validate_json(remote.bundled_text())
    return remote.LoadedData(data=data, source="bundled", revision=data.revision)


def fake_vinted(fill_seconds: float) -> VintedWorker:
    def fill(page, article, data, catalog, mode):
        time.sleep(fill_seconds)
        return filler.FillReport(mode=mode, status="ok", url=DRAFT_URL)

    return VintedWorker(
        start_playwright=_FakePlaywright,
        open_context=lambda playwright, **kw: _FakeContext(),
        is_logged_in=lambda page, data, **kw: True,
        fill=fill,
        load_data=_bundled_data,
        pause_range=(0.3, 0.6),
    )


@contextmanager
def _env(**values: str) -> Iterator[None]:
    saved = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@contextmanager
def running_app(capture: Path, *, delay: float, fill_seconds: float) -> Iterator[str]:
    """Démarre l'app sur un port libre ; rend l'adresse qui ouvre la session dans le navigateur."""
    if not (api_app.STATIC_DIR / "index.html").is_file():
        raise MissingFront("Front non compilé : lancer `npm run build` dans frontend/.")
    client = ReplayClient(capture, delay=delay)

    with (
        tempfile.TemporaryDirectory(prefix="kaloe-tutorial-", ignore_cleanup_errors=True) as tmp,
        # Licence « active » hors exécutable ; la clé Gemini de l'environnement est inutile ici.
        _env(VTO_DATA_DIR=tmp, VTO_DEV_LICENSE="1", GEMINI_API_KEY="tournage"),
    ):
        scenes.ensure_default_scenes()
        settings = config.load_settings()
        settings.tutorial = config.TutorialState(video_seen=True, tours_seen=list(TOURS))
        config.save_settings(settings)

        license_manager = LicenseManager()
        queue = GenerationQueue(lambda key: client, licensed=license_manager.licensed)
        vinted = fake_vinted(fill_seconds)
        queue.start()
        vinted.start()

        port, token = find_free_port(), secrets.token_urlsafe(16)
        app = api_app.create_app(
            token=token, port=port, queue=queue, vinted_worker=vinted,
            license_manager=license_manager,
        )
        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None, access_log=False)
        )
        thread = threading.Thread(target=server.run, name="tutorial-api", daemon=True)
        thread.start()
        try:
            if not _wait_until_ready(port):
                raise RuntimeError(f"L'API de tournage n'a pas démarré sur le port {port}.")
            yield login_url(port, token)
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            queue.stop()
            vinted.shutdown()
