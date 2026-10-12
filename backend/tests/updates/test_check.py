import threading

import pytest

from vto.updates import check
from vto.updates.check import UpdateChecker, compute_status
from vto.updates.manifest import Manifest, ManifestUnavailable


def make(version="0.3.0", minimum="0.2.0", notes="Nouveautés") -> Manifest:
    return Manifest(
        version=version,
        minimum_version=minimum,
        url=f"https://example.com/VirtualTryOn-Setup-{version}.exe",
        sha256="a" * 64,
        notes=notes,
    )


@pytest.mark.parametrize(
    ("current", "version", "minimum", "expected"),
    [
        ("0.3.0", "0.3.0", "0.2.0", "up_to_date"),
        ("0.4.0", "0.3.0", "0.2.0", "up_to_date"),  # version de dev plus récente
        ("0.2.0", "0.3.0", "0.2.0", "available"),
        ("0.2.9", "0.2.10", "0.2.0", "available"),
        ("0.3.0rc1", "0.3.0", "0.2.0", "available"),
        ("0.1.9", "0.3.0", "0.2.0", "required"),
        ("0.2.0rc1", "0.3.0", "0.2.0", "required"),
    ],
)
def test_compute_status(current, version, minimum, expected):
    assert compute_status(current, make(version, minimum)) == expected


class Fetcher:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = 0
        self.called = threading.Event()

    def __call__(self):
        self.calls += 1
        result = self.results[min(self.calls, len(self.results)) - 1]
        self.called.set()
        if isinstance(result, Exception):
            raise result
        return result


def test_snapshot_before_any_check():
    checker = UpdateChecker(current="0.2.0", fetch=Fetcher(make()), frozen=lambda: True)
    assert checker.snapshot() == {
        "current": "0.2.0",
        "latest": None,
        "status": "unknown",
        "notes": "",
        "can_install": True,
    }
    assert checker.manifest is None
    assert checker.is_required() is False


def test_check_now_available():
    checker = UpdateChecker(current="0.2.0", fetch=Fetcher(make()), frozen=lambda: False)
    checker.check_now()
    assert checker.snapshot() == {
        "current": "0.2.0",
        "latest": "0.3.0",
        "status": "available",
        "notes": "Nouveautés",
        "can_install": False,
    }
    assert checker.manifest == make()


def test_required():
    checker = UpdateChecker(current="0.1.0", fetch=Fetcher(make()))
    checker.check_now()
    assert checker.is_required() is True


def test_failure_keeps_last_valid_state(caplog):
    checker = UpdateChecker(
        current="0.1.0", fetch=Fetcher(make(), ManifestUnavailable("réseau coupé"))
    )
    checker.check_now()
    checker.check_now()
    assert checker.snapshot()["status"] == "required"
    assert "réseau coupé" in caplog.text


def test_failure_without_previous_state_is_unknown():
    checker = UpdateChecker(current="0.2.0", fetch=Fetcher(ManifestUnavailable("404")))
    checker.check_now()
    assert checker.snapshot()["status"] == "unknown"


def test_unexpected_error_does_not_kill_the_checker(caplog):
    checker = UpdateChecker(current="0.2.0", fetch=Fetcher(RuntimeError("bug")))
    checker.check_now()
    assert checker.snapshot()["status"] == "unknown"
    assert "bug" in caplog.text


def test_can_install_follows_frozen_by_default(monkeypatch):
    monkeypatch.setattr(check.paths, "is_frozen", lambda: True)
    assert UpdateChecker(current="0.2.0", fetch=Fetcher(make())).snapshot()["can_install"]


def test_thread_checks_at_start_then_periodically():
    fetcher = Fetcher(make())
    done = threading.Event()

    def fetch():
        result = fetcher()
        if fetcher.calls >= 3:
            done.set()
        return result

    checker = UpdateChecker(current="0.2.0", fetch=fetch, interval=0)
    checker.start()
    try:
        assert done.wait(5)
    finally:
        checker.stop()
    assert fetcher.calls >= 3
    assert checker.snapshot()["status"] == "available"


def test_stop_ends_the_thread_quickly():
    fetcher = Fetcher(make())
    checker = UpdateChecker(current="0.2.0", fetch=fetcher, interval=3600)
    checker.start()
    assert fetcher.called.wait(5)
    checker.stop(timeout=5)
    assert not checker.is_alive()
