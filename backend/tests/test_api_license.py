import pytest

from vto.licensing import LicenseError
from vto.licensing.client import LicenseRefused, LicenseUnreachable
from vto.licensing.state import BAD_FORMAT

KEY = "VTO-ABCD-EFGH-JKMN-WXYZ"


class FakeManager:
    def __init__(self):
        self.key = None
        self.fail: Exception | None = None
        self.calls = []

    def snapshot(self):
        return {
            "state": "active" if self.key else "none",
            "key_hint": f"VTO-…-{self.key[-4:]}" if self.key else None,
            "status": "active" if self.key else None,
            "period_end": 1_800_000_000 if self.key else None,
            "devices_max": 2,
            "message": None,
        }

    def _maybe_fail(self):
        if self.fail:
            raise self.fail

    def activate(self, text):
        self.calls.append(("activate", text))
        self._maybe_fail()
        self.key = KEY

    def deactivate(self):
        self.calls.append(("deactivate",))
        self._maybe_fail()
        self.key = None

    def portal_url(self):
        self.calls.append(("portal",))
        self._maybe_fail()
        return "https://billing.stripe.test/s"

    def renew_url(self):
        self.calls.append(("renew",))
        self._maybe_fail()
        return f"https://licence.test/renouveler?cle={KEY}"


@pytest.fixture
def manager():
    return FakeManager()


@pytest.fixture
def lapi(make_api, fake, manager):
    return make_api(lambda key: fake, license_manager=manager)


def test_get_without_license(lapi, monkeypatch):
    monkeypatch.setenv("VTO_LICENSE_URL", "https://licence.test")
    r = lapi.get("/api/license")
    assert r.status_code == 200
    assert r.json()["state"] == "none"
    assert r.json()["site_url"] == "https://licence.test"


def test_activate_returns_the_state_with_a_hint_only(lapi, manager):
    r = lapi.post("/api/license", json={"key": "vto abcd efgh jkmn wxyz"})
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "active"
    assert body["key_hint"] == "VTO-…-WXYZ"
    assert KEY not in r.text
    assert manager.calls == [("activate", "vto abcd efgh jkmn wxyz")]
    assert KEY not in lapi.get("/api/license").text


@pytest.mark.parametrize(
    ("error", "status", "message"),
    [
        (LicenseError(BAD_FORMAT), 400, BAD_FORMAT),
        (LicenseRefused("unknown_key"), 400, "Cette clé de licence n'existe pas."),
        (LicenseRefused("too_many_devices", ["A", "B"]), 400, "2 PC (A, B)"),
        (LicenseRefused("expired"), 400, "Ton abonnement est terminé."),
        (LicenseUnreachable(), 503, "Impossible de vérifier ton abonnement."),
    ],
)
def test_activate_errors(lapi, manager, error, status, message):
    manager.fail = error
    r = lapi.post("/api/license", json={"key": KEY})
    assert r.status_code == status
    assert message in r.json()["message"]


def test_activate_requires_a_key(lapi):
    assert lapi.post("/api/license", json={}).status_code == 422


def test_deactivate(lapi, manager):
    lapi.post("/api/license", json={"key": KEY})
    r = lapi.delete("/api/license")
    assert r.status_code == 200
    assert r.json()["state"] == "none"
    assert manager.calls[-1] == ("deactivate",)


def test_deactivate_unreachable(lapi, manager):
    manager.fail = LicenseUnreachable()
    assert lapi.delete("/api/license").status_code == 503


def test_portal(lapi, manager):
    r = lapi.get("/api/license/portal")
    assert r.status_code == 200
    assert r.json() == {"url": "https://billing.stripe.test/s"}


def test_portal_without_active_license(lapi, manager):
    manager.fail = LicenseError()
    r = lapi.get("/api/license/portal")
    assert r.status_code == 400
    assert r.json()["message"] == "Cette action demande un abonnement actif."


def test_renew(lapi, manager):
    r = lapi.get("/api/license/renew")
    assert r.status_code == 200
    assert r.json() == {"url": f"https://licence.test/renouveler?cle={KEY}"}


def test_renew_without_license(lapi, manager):
    manager.fail = LicenseError("Aucune licence sur ce PC.")
    r = lapi.get("/api/license/renew")
    assert r.status_code == 400
    assert r.json()["message"] == "Aucune licence sur ce PC."


def test_without_manager_state_is_none(api):
    assert api.get("/api/license").json()["state"] == "none"
    assert api.post("/api/license", json={"key": KEY}).status_code == 503


def test_requires_session(make_api, fake, manager):
    client = make_api(lambda key: fake, license_manager=manager, login=False)
    assert client.get("/api/license").status_code == 401
