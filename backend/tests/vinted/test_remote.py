import json
import logging
import os
from typing import get_args

import httpx
import pytest

from samples import minimal
from vto.core import paths
from vto.vinted import remote, schema


def payload(revision="2026-10-11.1") -> bytes:
    return json.dumps({**minimal(), "revision": revision}).encode()


@pytest.fixture
def bundled(monkeypatch):
    """Copie embarquée de test (la vraie arrive avec la tâche 5)."""
    monkeypatch.setattr(remote, "bundled_text", lambda: payload("embarquée").decode())


class Server:
    """Transport factice : enregistre les requêtes, renvoie la réponse programmée."""

    def __init__(self, handler):
        self.handler = handler
        self.requests: list[httpx.Request] = []

    def transport(self):
        def handle(request):
            self.requests.append(request)
            return self.handler(request)

        return httpx.MockTransport(handle)


def serve(status=200, content=b"", headers=None):
    return Server(lambda request: httpx.Response(status, content=content, headers=headers))


def fail(exc):
    def handler(request):
        raise exc

    return Server(handler)


def load(server):
    return remote.load_vinted_data(transport=server.transport())


def cache_file():
    return paths.cache_dir() / "vinted-v1.json"


def etag_file():
    return paths.cache_dir() / "vinted-v1.etag"


def fill_cache(revision="cache", etag='"v1"'):
    cache_file().write_bytes(payload(revision))
    etag_file().write_text(etag, encoding="utf-8")


def test_valid_remote_is_used_and_cached(data_dir, bundled, caplog):
    caplog.set_level(logging.INFO)
    server = serve(content=payload("distante"), headers={"ETag": '"v2"'})
    loaded = load(server)
    assert (loaded.source, loaded.revision) == ("remote", "distante")
    assert loaded.data.revision == "distante"
    assert json.loads(cache_file().read_bytes())["revision"] == "distante"
    assert etag_file().read_text(encoding="utf-8") == '"v2"'
    assert server.requests[0].url == remote.DEFAULT_URL
    assert "If-None-Match" not in server.requests[0].headers
    assert "remote" in caplog.text and "distante" in caplog.text


def test_etag_is_sent_and_304_uses_cache(data_dir, bundled):
    fill_cache(etag='"v1"')
    server = serve(304)
    loaded = load(server)
    assert server.requests[0].headers["If-None-Match"] == '"v1"'
    assert (loaded.source, loaded.revision) == ("cache", "cache")


def test_remote_without_etag_forgets_old_one(data_dir, bundled):
    fill_cache()
    load(serve(content=payload("distante")))
    assert not etag_file().exists()


FAILURES = {
    "json invalide": serve(content=b"{pas du json"),
    "schéma invalide": serve(content=json.dumps({"format": 2}).encode()),
    "erreur serveur": serve(500),
    "introuvable": serve(404),
    "délai dépassé": fail(httpx.ReadTimeout("trop long")),
    "réseau coupé": fail(httpx.ConnectError("hors ligne")),
}


@pytest.mark.parametrize("server", FAILURES.values(), ids=FAILURES.keys())
def test_failure_falls_back_to_valid_cache(data_dir, bundled, server, caplog):
    fill_cache()
    loaded = load(server)
    assert (loaded.source, loaded.revision) == ("cache", "cache")
    assert json.loads(cache_file().read_bytes())["revision"] == "cache"  # cache intact
    assert "repli" in caplog.text


@pytest.mark.parametrize("server", FAILURES.values(), ids=FAILURES.keys())
def test_failure_without_cache_uses_bundled(data_dir, bundled, server):
    loaded = load(server)
    assert (loaded.source, loaded.revision) == ("bundled", "embarquée")


def test_corrupted_cache_and_no_network_uses_bundled(data_dir, bundled, caplog):
    cache_file().write_text("{abîmé", encoding="utf-8")
    etag_file().write_text('"v1"', encoding="utf-8")
    server = fail(httpx.ConnectError("hors ligne"))
    loaded = load(server)
    assert loaded.source == "bundled"
    assert "If-None-Match" not in server.requests[0].headers  # cache inutilisable : pas d'ETag
    assert "cache" in caplog.text


def test_304_without_usable_cache_uses_bundled(data_dir, bundled):
    assert load(serve(304)).source == "bundled"


def test_url_can_be_overridden(data_dir, bundled, monkeypatch):
    monkeypatch.setenv("VTO_VINTED_DATA_URL", "http://127.0.0.1:9/vinted.json")
    server = serve(content=payload())
    load(server)
    assert str(server.requests[0].url) == "http://127.0.0.1:9/vinted.json"


def test_cache_write_is_atomic(data_dir, bundled, monkeypatch):
    fill_cache()

    def boom(*args, **kwargs):
        raise OSError("disque plein")

    monkeypatch.setattr(os, "replace", boom)
    loaded = load(serve(content=payload("distante"), headers={"ETag": '"v2"'}))
    assert loaded.revision == "distante"  # les données téléchargées restent utilisables
    assert json.loads(cache_file().read_bytes())["revision"] == "cache"
    assert not list(paths.cache_dir().glob("*.tmp"))



def test_default_url_is_numbered_by_format():
    assert schema.FORMAT == 1
    assert get_args(schema.VintedData.model_fields["format"].annotation) == (schema.FORMAT,)
    assert remote.DEFAULT_URL.endswith(f"/main/data/vinted-v{schema.FORMAT}.json")


def test_unnumbered_cache_is_ignored(data_dir, bundled):
    (paths.cache_dir() / "vinted.json").write_text("{}", encoding="utf-8")
    loaded = load(serve(status=500))
    assert loaded.source == "bundled"
