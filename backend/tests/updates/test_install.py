import hashlib
import threading

import httpx
import pytest

from vto.core import paths
from vto.updates import UpdateError, install
from vto.updates.install import Installer, clean_old_installers, installer_args
from vto.updates.manifest import Manifest

CONTENT = b"MZ" + b"x" * 200_000


def make(content=CONTENT, version="0.3.0") -> Manifest:
    return Manifest(
        version=version,
        minimum_version="0.2.0",
        url=f"https://example.com/Kaloe-Setup-{version}.exe",
        sha256=hashlib.sha256(content).hexdigest(),
    )


def serve(content=CONTENT, status=200):
    return httpx.MockTransport(lambda request: httpx.Response(status, content=content))


class Launcher:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[list[str]] = []

    def __call__(self, args):
        self.calls.append(args)
        if self.error:
            raise self.error


class Shutdown:
    def __init__(self):
        self.called = threading.Event()

    def __call__(self):
        self.called.set()


def make_installer(transport=None, launcher=None, shutdown=None):
    return Installer(
        launcher=launcher or Launcher(),
        on_launched=shutdown or Shutdown(),
        transport=transport or serve(),
    )


def test_success_downloads_verifies_launches_then_shuts_down(data_dir):
    launcher, shutdown = Launcher(), Shutdown()
    installer = make_installer(launcher=launcher, shutdown=shutdown)
    installer.run(make())
    target = paths.updates_cache_dir() / "Kaloe-Setup-0.3.0.exe"
    assert target.read_bytes() == CONTENT
    assert launcher.calls == [installer_args(target, "0.3.0")]
    assert shutdown.called.is_set()
    progress = installer.progress()
    assert progress["state"] == "launching"
    assert progress["received"] == progress["total"] == len(CONTENT)


def test_installer_args(data_dir):
    target = paths.updates_cache_dir() / "Kaloe-Setup-0.3.0.exe"
    assert installer_args(target, "0.3.0") == [
        str(target),
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        f"/LOG={paths.logs_dir() / 'update-0.3.0.log'}",
    ]


def test_progress_is_visible_during_download(data_dir, monkeypatch):
    monkeypatch.setattr(install, "CHUNK", 50_000)
    seen = []

    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            for i in range(0, len(CONTENT), 50_000):
                seen.append(installer.progress()["received"])
                yield CONTENT[i : i + 50_000]

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, stream=Stream(), headers={"Content-Length": str(len(CONTENT))}
        )
    )
    installer = make_installer(transport=transport)
    installer.run(make())
    assert seen[0] == 0 and seen[-1] > 0
    assert installer.progress()["total"] == len(CONTENT)


def test_bad_checksum_deletes_the_file(data_dir):
    launcher, shutdown = Launcher(), Shutdown()
    installer = make_installer(transport=serve(b"autre"), launcher=launcher, shutdown=shutdown)
    installer.run(make())
    assert installer.progress()["state"] == "error"
    assert "abîmée" in installer.progress()["message"]
    assert list(paths.updates_cache_dir().iterdir()) == []
    assert launcher.calls == [] and not shutdown.called.is_set()


@pytest.mark.parametrize("transport", [serve(status=404), None])
def test_download_failure(data_dir, transport):
    if transport is None:

        def fail(request):
            raise httpx.ConnectError("coupé")

        transport = httpx.MockTransport(fail)
    installer = make_installer(transport=transport)
    installer.run(make())
    progress = installer.progress()
    assert progress["state"] == "error"
    assert "téléchargement" in progress["message"]
    assert list(paths.updates_cache_dir().iterdir()) == []


def test_blocked_launch_keeps_the_app_open(data_dir):
    shutdown = Shutdown()
    installer = make_installer(launcher=Launcher(PermissionError("bloqué")), shutdown=shutdown)
    installer.run(make())
    assert installer.progress()["state"] == "error"
    assert "Windows a bloqué" in installer.progress()["message"]
    assert not shutdown.called.is_set()


def test_start_runs_in_background_and_refuses_a_second_start(data_dir):
    gate = threading.Event()

    def slow(request):
        gate.wait(5)
        return httpx.Response(200, content=CONTENT)

    shutdown = Shutdown()
    installer = make_installer(transport=httpx.MockTransport(slow), shutdown=shutdown)
    installer.start(make())
    assert installer.progress()["state"] == "downloading"
    with pytest.raises(UpdateError):
        installer.start(make())
    gate.set()
    assert shutdown.called.wait(5)


def test_restart_after_error(data_dir):
    installer = make_installer(transport=serve(b"autre"))
    installer.run(make())
    assert installer.progress()["state"] == "error"
    installer._transport = serve()
    installer.run(make())
    assert installer.progress()["state"] == "launching"
    assert installer.progress()["message"] is None


def test_clean_old_installers_only_removes_installers(data_dir):
    folder = paths.updates_cache_dir()
    (folder / "Kaloe-Setup-0.2.0.exe").write_bytes(b"x")
    (folder / "Kaloe-Setup-0.3.0.exe.part").write_bytes(b"x")
    keep = folder / "lisez-moi.txt"
    keep.write_text("x", encoding="utf-8")
    clean_old_installers()
    assert list(folder.iterdir()) == [keep]


def test_download_sends_the_license_token_to_the_worker(data_dir, monkeypatch):
    monkeypatch.setenv("VTO_LICENSE_URL", "https://example.com")
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(200, content=CONTENT)

    installer = Installer(
        launcher=Launcher(),
        on_launched=Shutdown(),
        transport=httpx.MockTransport(handle),
        token=lambda: "jeton",
    )
    installer.run(make())
    assert seen[0].headers["Authorization"] == "Bearer jeton"


def test_download_without_token_sends_no_authorization(data_dir, monkeypatch):
    monkeypatch.setenv("VTO_LICENSE_URL", "https://example.com")
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(200, content=CONTENT)

    Installer(
        launcher=Launcher(), on_launched=Shutdown(), transport=httpx.MockTransport(handle)
    ).run(make())
    assert "Authorization" not in seen[0].headers
