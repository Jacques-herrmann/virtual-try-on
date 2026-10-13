import json

import httpx
import pytest

from vto.licensing import LicenseError
from vto.licensing import client as client_mod
from vto.licensing.client import LicenseClient, LicenseRefused, LicenseUnreachable

BASE = "https://licence.test"


class Server:
    def __init__(self, handler):
        self.handler = handler
        self.requests: list[httpx.Request] = []

    def client(self, base_url=BASE) -> LicenseClient:
        def handle(request):
            self.requests.append(request)
            return self.handler(request)

        return LicenseClient(base_url=base_url, transport=httpx.MockTransport(handle))


def answer(status=200, body=None):
    return Server(lambda request: httpx.Response(status, json=body))


def refused(code, **extra):
    return answer(400 if code == "bad_request" else 403, {"code": code, "message": "x", **extra})


def test_activate_sends_key_device_and_name():
    server = answer(body={"token": "jeton"})
    token = server.client().activate("VTO-ABCD-EFGH-JKMN-PQRS", "dev-1", "Bureau")
    assert token == "jeton"
    req = server.requests[0]
    assert req.method == "POST"
    assert str(req.url) == f"{BASE}/api/activate"
    assert json.loads(req.content) == {
        "key": "VTO-ABCD-EFGH-JKMN-PQRS",
        "device_id": "dev-1",
        "device_name": "Bureau",
    }


def test_refresh_sends_key_and_device():
    server = answer(body={"token": "jeton2"})
    assert server.client().refresh("VTO-ABCD-EFGH-JKMN-PQRS", "dev-1") == "jeton2"
    assert str(server.requests[0].url) == f"{BASE}/api/token"
    assert json.loads(server.requests[0].content) == {
        "key": "VTO-ABCD-EFGH-JKMN-PQRS",
        "device_id": "dev-1",
    }


def test_deactivate():
    server = answer(body={"ok": True})
    server.client().deactivate("VTO-ABCD-EFGH-JKMN-PQRS", "dev-1")
    assert str(server.requests[0].url) == f"{BASE}/api/deactivate"


def test_base_url_trailing_slash_is_ignored():
    server = answer(body={"token": "t"})
    server.client(base_url=BASE + "/").refresh("k", "d")
    assert str(server.requests[0].url) == f"{BASE}/api/token"


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (
            "unknown_key",
            "Cette clé de licence n'existe pas. Vérifie-la dans l'e-mail reçu après l'achat.",
        ),
        (
            "expired",
            "Ton abonnement est terminé. "
            "Renouvelle-le pour continuer à générer et à envoyer sur Vinted.",
        ),
        ("not_activated", "Ce PC n'est pas activé avec cette clé."),
    ],
)
def test_refusals_become_french_license_errors(code, expected):
    with pytest.raises(LicenseRefused) as info:
        refused(code).client().activate("k", "d", "n")
    assert info.value.code == code
    assert info.value.user_message == expected
    assert isinstance(info.value, LicenseError)


def test_too_many_devices_names_the_devices():
    with pytest.raises(LicenseRefused) as info:
        refused("too_many_devices", devices=["Bureau", "Portable"]).client().activate("k", "d", "n")
    assert info.value.code == "too_many_devices"
    assert info.value.user_message == (
        "Ta clé est déjà utilisée sur 2 PC (Bureau, Portable). "
        "Désactive-la sur l'un d'eux, ou attends 30 jours sans utilisation."
    )


def test_network_error_is_unreachable():
    def boom(request):
        raise httpx.ConnectError("hors ligne")

    with pytest.raises(LicenseUnreachable) as info:
        Server(boom).client().refresh("k", "d")
    assert info.value.user_message == (
        "Impossible de vérifier ton abonnement. Vérifie ta connexion Internet."
    )


@pytest.mark.parametrize("status", [500, 502, 503])
def test_server_error_is_unreachable(status):
    with pytest.raises(LicenseUnreachable):
        answer(status, {"code": "unavailable"}).client().refresh("k", "d")


def test_unknown_answer_is_unreachable():
    server = Server(lambda r: httpx.Response(404, text="<html>"))
    with pytest.raises(LicenseUnreachable):
        server.client().refresh("k", "d")


def test_missing_token_is_unreachable():
    with pytest.raises(LicenseUnreachable):
        answer(200, {"autre": 1}).client().refresh("k", "d")


def test_portal_url_from_redirect():
    server = Server(
        lambda r: httpx.Response(302, headers={"Location": "https://billing.stripe.com/p/s"})
    )
    assert server.client().portal_url("jeton") == "https://billing.stripe.com/p/s"
    req = server.requests[0]
    assert req.method == "GET"
    assert str(req.url) == f"{BASE}/api/portal"
    assert req.headers["Authorization"] == "Bearer jeton"


def test_portal_refused_is_unreachable():
    with pytest.raises(LicenseUnreachable):
        answer(401, {"code": "unauthorized"}).client().portal_url("jeton")


def test_bearer_only_for_the_license_worker(monkeypatch):
    monkeypatch.setenv("VTO_LICENSE_URL", "https://licence.test")
    assert client_mod.bearer("https://licence.test/updates/latest.json", "t") == {
        "Authorization": "Bearer t"
    }
    assert client_mod.bearer("https://licence.test/updates/latest.json", None) == {}
    assert client_mod.bearer("https://github.com/x/latest.json", "t") == {}
    assert client_mod.bearer("https://licence.test.evil.com/x", "t") == {}
    assert client_mod.bearer("http://licence.test/x", "t") == {}


def test_default_url_and_override(monkeypatch):
    monkeypatch.delenv("VTO_LICENSE_URL", raising=False)
    assert client_mod.license_url() == client_mod.DEFAULT_URL
    assert client_mod.DEFAULT_URL.startswith("https://")
    monkeypatch.setenv("VTO_LICENSE_URL", "http://127.0.0.1:8787/")
    assert client_mod.license_url() == "http://127.0.0.1:8787"
