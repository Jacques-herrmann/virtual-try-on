import pytest

from vto.updates import UpdateError
from vto.updates.install import ALREADY_RUNNING
from vto.updates.manifest import Manifest

MANIFEST = Manifest(
    version="0.3.0",
    minimum_version="0.2.0",
    url="https://example.com/VirtualTryOn-Setup-0.3.0.exe",
    sha256="a" * 64,
    notes="Nouveautés",
)


class FakeChecker:
    def __init__(self, status="available", can_install=True, manifest=MANIFEST):
        self.status = status
        self.can_install = can_install
        self.manifest = manifest

    def snapshot(self):
        return {
            "current": "0.2.0",
            "latest": self.manifest.version if self.manifest else None,
            "status": self.status,
            "notes": self.manifest.notes if self.manifest else "",
            "can_install": self.can_install,
        }

    def is_required(self):
        return self.status == "required"


class FakeInstaller:
    def __init__(self):
        self.started = []
        self.state = "idle"

    def start(self, manifest):
        if self.state == "downloading":
            raise UpdateError(ALREADY_RUNNING)
        self.started.append(manifest)
        self.state = "downloading"

    def progress(self):
        return {"state": self.state, "received": 0, "total": None, "message": None}


class FakeQueue:
    def __init__(self, busy=False):
        self.busy = busy

    def is_busy(self):
        return self.busy


@pytest.fixture
def checker():
    return FakeChecker()


@pytest.fixture
def installer():
    return FakeInstaller()


@pytest.fixture
def uapi(make_api, fake, checker, installer):
    return make_api(lambda key: fake, update_checker=checker, installer=installer)


def test_snapshot(uapi):
    assert uapi.get("/api/update").json() == {
        "current": "0.2.0",
        "latest": "0.3.0",
        "status": "available",
        "notes": "Nouveautés",
        "can_install": True,
    }


@pytest.mark.parametrize("status", ["available", "required"])
def test_install_starts(uapi, installer, status, checker):
    checker.status = status
    r = uapi.post("/api/update/install")
    assert r.status_code == 202
    assert r.json()["state"] == "downloading"
    assert installer.started == [MANIFEST]


def test_second_install_is_refused(uapi):
    assert uapi.post("/api/update/install").status_code == 202
    r = uapi.post("/api/update/install")
    assert r.status_code == 409
    assert r.json()["message"] == ALREADY_RUNNING


def test_install_refused_outside_installed_app(uapi, checker, installer):
    checker.can_install = False
    r = uapi.post("/api/update/install")
    assert r.status_code == 409
    assert "application installée" in r.json()["message"]
    assert installer.started == []


@pytest.mark.parametrize(
    ("status", "manifest"), [("up_to_date", MANIFEST), ("unknown", None)]
)
def test_install_refused_when_nothing_to_install(uapi, checker, installer, status, manifest):
    checker.status, checker.manifest = status, manifest
    r = uapi.post("/api/update/install")
    assert r.status_code == 409
    assert "Aucune mise à jour" in r.json()["message"]
    assert installer.started == []


def test_install_refused_while_generating(make_api, fake, checker, installer, monkeypatch):
    api = make_api(lambda key: fake, update_checker=checker, installer=installer)
    monkeypatch.setattr(api.app.state, "queue", FakeQueue(busy=True))
    r = api.post("/api/update/install")
    assert r.status_code == 409
    assert "génération est en cours" in r.json()["message"]
    assert installer.started == []


def test_install_refused_while_vinted_works(make_api, fake, checker, installer):
    from fakes import FakeVintedWorker
    from samples import loaded_data

    worker = FakeVintedWorker(loaded_data())
    worker.busy = True
    api = make_api(
        lambda key: fake, update_checker=checker, installer=installer, vinted_worker=worker
    )
    r = api.post("/api/update/install")
    assert r.status_code == 409
    assert "Vinted" in r.json()["message"]
    assert installer.started == []


def test_progress(uapi):
    uapi.post("/api/update/install")
    assert uapi.get("/api/update/progress").json() == {
        "state": "downloading",
        "received": 0,
        "total": None,
        "message": None,
    }


def test_default_app_has_unknown_status(api):
    body = api.get("/api/update").json()
    assert body["status"] == "unknown" and body["can_install"] is False
