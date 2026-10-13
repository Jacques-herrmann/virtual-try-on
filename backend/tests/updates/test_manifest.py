import json

import httpx
import pytest

from vto.updates import manifest
from vto.updates.manifest import Manifest, ManifestUnavailable

SHA = "a" * 64


def body(**changes) -> dict:
    data = {
        "version": "0.3.0",
        "minimum_version": "0.2.0",
        "url": "https://github.com/x/y/releases/download/v0.3.0/Kaloe-Setup-0.3.0.exe",
        "sha256": SHA,
        "notes": "Nouveautés",
    }
    data.update(changes)
    return {k: v for k, v in data.items() if v is not None}


class Server:
    def __init__(self, handler):
        self.handler = handler
        self.requests: list[httpx.Request] = []

    def transport(self):
        def handle(request):
            self.requests.append(request)
            return self.handler(request)

        return httpx.MockTransport(handle)


def serve(status=200, content=None):
    raw = json.dumps(body()).encode() if content is None else content
    return Server(lambda request: httpx.Response(status, content=raw))


def test_valid_manifest():
    m = manifest.fetch_manifest(transport=serve().transport())
    assert m == Manifest(**body())


def test_default_url_is_the_license_worker(monkeypatch):
    monkeypatch.delenv("VTO_UPDATE_URL", raising=False)
    monkeypatch.setenv("VTO_LICENSE_URL", "https://licence.test")
    server = serve()
    manifest.fetch_manifest(transport=server.transport())
    assert str(server.requests[0].url) == "https://licence.test/updates/latest.json"


def test_token_is_sent_to_the_worker(monkeypatch):
    monkeypatch.delenv("VTO_UPDATE_URL", raising=False)
    monkeypatch.setenv("VTO_LICENSE_URL", "https://licence.test")
    server = serve()
    manifest.fetch_manifest(transport=server.transport(), token="jeton")
    assert server.requests[0].headers["Authorization"] == "Bearer jeton"


def test_no_authorization_without_token(monkeypatch):
    monkeypatch.setenv("VTO_LICENSE_URL", "https://licence.test")
    server = serve()
    manifest.fetch_manifest(transport=server.transport())
    assert "Authorization" not in server.requests[0].headers


def test_refused_token_is_unavailable(monkeypatch):
    monkeypatch.setenv("VTO_LICENSE_URL", "https://licence.test")
    with pytest.raises(ManifestUnavailable):
        manifest.fetch_manifest(transport=serve(status=401).transport(), token="vieux")


def test_redirects_are_followed():
    def handler(request):
        if request.url.path.endswith("/latest/download/latest.json"):
            return httpx.Response(302, headers={"Location": "https://cdn.example/latest.json"})
        return httpx.Response(200, content=json.dumps(body()).encode())

    assert manifest.fetch_manifest(transport=Server(handler).transport()).version == "0.3.0"


def test_env_url_wins(monkeypatch):
    monkeypatch.setenv("VTO_UPDATE_URL", "https://worker.example/latest.json")
    server = serve()
    manifest.fetch_manifest(transport=server.transport())
    assert str(server.requests[0].url) == "https://worker.example/latest.json"


def test_local_http_url_is_allowed(monkeypatch):
    monkeypatch.setenv("VTO_UPDATE_URL", "http://127.0.0.1:8000/latest.json")
    local = body(url="http://127.0.0.1:8000/Kaloe-Setup-0.3.0.exe")
    server = serve(content=json.dumps(local).encode())
    assert manifest.fetch_manifest(transport=server.transport()).url.startswith("http://127")


def test_remote_http_url_is_refused(monkeypatch):
    monkeypatch.setenv("VTO_UPDATE_URL", "http://worker.example/latest.json")
    server = serve()
    with pytest.raises(ManifestUnavailable):
        manifest.fetch_manifest(transport=server.transport())
    assert server.requests == []


def test_unknown_field_is_ignored():
    raw = json.dumps({**body(), "channel": "stable"}).encode()
    assert manifest.fetch_manifest(transport=serve(content=raw).transport()).version == "0.3.0"


def test_empty_notes_are_accepted():
    raw = json.dumps(body(notes="")).encode()
    assert manifest.fetch_manifest(transport=serve(content=raw).transport()).notes == ""


@pytest.mark.parametrize(
    "changes",
    [
        {"sha256": None},
        {"url": "http://github.com/setup.exe"},
        {"url": "ftp://github.com/setup.exe"},
        {"sha256": "abc"},
        {"sha256": "g" * 64},
        {"version": "pas une version"},
        {"minimum_version": "1.0.0"},  # plus récente que la version publiée
    ],
)
def test_invalid_manifest_is_unavailable(changes):
    raw = json.dumps(body(**changes)).encode()
    with pytest.raises(ManifestUnavailable):
        manifest.fetch_manifest(transport=serve(content=raw).transport())


@pytest.mark.parametrize("server", [serve(status=404), serve(content=b"{pas du json")])
def test_http_error_or_bad_json_is_unavailable(server):
    with pytest.raises(ManifestUnavailable):
        manifest.fetch_manifest(transport=server.transport())


def test_network_error_is_unavailable():
    def handler(request):
        raise httpx.ConnectTimeout("délai dépassé")

    with pytest.raises(ManifestUnavailable):
        manifest.fetch_manifest(transport=Server(handler).transport())
