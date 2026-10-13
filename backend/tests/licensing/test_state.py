import json
import os
import threading

import pytest
from signing import KEY, NOW, PUBLIC_KEYS, make_token

from vto.core import paths
from vto.licensing import LicenseError
from vto.licensing.client import LicenseRefused, LicenseUnreachable
from vto.licensing.state import LicenseManager


class FakeClient:
    """Worker simulé : chaque méthode rend un jeton pour le PC demandé, ou lève l'erreur prévue."""

    def __init__(self):
        self.calls: list[tuple] = []
        self.fail: dict[str, Exception] = {}
        self.status = "active"
        self.exp: int | None = None
        self.refreshed = threading.Event()

    def _token(self, device_id, key):
        return make_token(device_id, key=key, status=self.status, exp=self.exp)

    def activate(self, key, device_id, device_name):
        self.calls.append(("activate", key, device_id, device_name))
        if "activate" in self.fail:
            raise self.fail["activate"]
        return self._token(device_id, key)

    def refresh(self, key, device_id):
        self.calls.append(("refresh", key, device_id))
        self.refreshed.set()
        if "refresh" in self.fail:
            raise self.fail["refresh"]
        return self._token(device_id, key)

    def deactivate(self, key, device_id):
        self.calls.append(("deactivate", key, device_id))
        if "deactivate" in self.fail:
            raise self.fail["deactivate"]

    def portal_url(self, token):
        self.calls.append(("portal", token))
        return "https://billing.stripe.test/s"


class Clock:
    def __init__(self, t=NOW):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def worker():
    return FakeClient()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def make_manager(data_dir, worker, clock, monkeypatch):
    monkeypatch.delenv("VTO_DEV_LICENSE", raising=False)
    made = []

    def _make(**kw):
        kw.setdefault("client", worker)
        kw.setdefault("public_keys", PUBLIC_KEYS)
        kw.setdefault("now", clock)
        kw.setdefault("frozen", lambda: True)
        kw.setdefault("device_name", lambda: "Bureau")
        manager = LicenseManager(**kw)
        made.append(manager)
        return manager

    yield _make
    for m in made:
        m.stop()


def stored():
    return json.loads((paths.data_dir() / "license.json").read_text(encoding="utf-8"))


def write(data):
    (paths.data_dir() / "license.json").write_text(json.dumps(data), encoding="utf-8")


# --- identité du PC et persistance ---


def test_device_id_is_created_once_and_kept(make_manager):
    first = make_manager().device_id
    assert len(first) == 36
    assert make_manager().device_id == first
    assert stored()["device_id"] == first


def test_license_file_is_written_atomically(make_manager, monkeypatch):
    replaced = []
    real = os.replace

    def spy(a, b):
        replaced.append((a, b))
        real(a, b)

    monkeypatch.setattr(os, "replace", spy)
    make_manager().activate(KEY)
    assert replaced and all(str(b).endswith("license.json") for _, b in replaced)
    assert not list(paths.data_dir().glob("*.tmp"))


def test_unreadable_license_file_starts_fresh(make_manager):
    (paths.data_dir() / "license.json").write_text("{pas du json", encoding="utf-8")
    manager = make_manager()
    assert manager.state() == "none"
    assert manager.device_id


# --- états ---


def test_state_none_without_key(make_manager):
    manager = make_manager()
    assert manager.state() == "none"
    assert not manager.licensed()
    assert manager.token() is None


def test_activate_stores_key_and_token(make_manager, worker):
    manager = make_manager()
    manager.activate("  vto abcd efgh jkmn pqrs ")
    assert worker.calls == [("activate", KEY, manager.device_id, "Bureau")]
    assert manager.state() == "active"
    assert manager.licensed()
    assert stored()["key"] == KEY
    assert manager.token() == stored()["token"]


def test_activate_refuses_a_malformed_key_without_calling(make_manager, worker):
    with pytest.raises(LicenseError) as info:
        make_manager().activate("n'importe quoi")
    assert info.value.user_message == (
        "Cette clé n'a pas le bon format. Elle ressemble à VTO-XXXX-XXXX-XXXX-XXXX."
    )
    assert worker.calls == []


def test_activate_refused_keeps_previous_state(make_manager, worker):
    manager = make_manager()
    worker.fail["activate"] = LicenseRefused("unknown_key")
    with pytest.raises(LicenseRefused):
        manager.activate(KEY)
    assert manager.state() == "none"
    assert "key" not in stored()


def test_activate_unreachable_raises(make_manager, worker):
    worker.fail["activate"] = LicenseUnreachable()
    with pytest.raises(LicenseUnreachable):
        make_manager().activate(KEY)


def test_valid_token_and_unreachable_worker_stay_active(make_manager, worker):
    manager = make_manager()
    manager.activate(KEY)
    worker.fail["refresh"] = LicenseUnreachable()
    manager.refresh_now()
    assert manager.state() == "active"


def test_expired_token_and_unreachable_worker_are_unverified(make_manager, worker, clock):
    manager = make_manager()
    manager.activate(KEY)
    worker.fail["refresh"] = LicenseUnreachable()
    clock.t = NOW + 7 * 86400
    manager.refresh_now()
    assert manager.state() == "unverified"
    assert not manager.licensed()
    assert manager.token() is None


def test_ended_subscription_from_worker_is_expired(make_manager, worker):
    manager = make_manager()
    manager.activate(KEY)
    worker.fail["refresh"] = LicenseRefused("expired")
    manager.refresh_now()
    assert manager.state() == "expired"
    assert manager.token() is None
    assert stored()["key"] == KEY  # la clé reste : un réabonnement la réutilise


def test_expired_activation_is_expired(make_manager, worker):
    manager = make_manager()
    worker.fail["activate"] = LicenseRefused("expired")
    with pytest.raises(LicenseRefused):
        manager.activate(KEY)
    assert manager.state() == "expired"
    assert stored()["key"] == KEY


def test_token_with_ended_status_is_expired(make_manager, worker):
    worker.status = "canceled"
    manager = make_manager()
    manager.activate(KEY)
    assert manager.state() == "expired"


def test_renewal_after_expiry_is_active_again(make_manager, worker):
    manager = make_manager()
    manager.activate(KEY)
    worker.fail["refresh"] = LicenseRefused("expired")
    manager.refresh_now()
    del worker.fail["refresh"]
    manager.refresh_now()
    assert manager.state() == "active"


def test_state_survives_a_restart(make_manager):
    make_manager().activate(KEY)
    assert make_manager().state() == "active"


def test_token_of_another_device_is_ignored(make_manager):
    make_manager().activate(KEY)
    data = stored()
    data["token"] = make_token("autre-pc")
    write(data)
    assert make_manager().state() == "unverified"


# --- rafraîchissement ---


def test_refresh_replaces_the_token(make_manager, worker, clock):
    manager = make_manager()
    manager.activate(KEY)
    old = manager.token()
    clock.t = NOW + 3600
    worker.exp = NOW + 3600 + 7 * 86400
    manager.refresh_now()
    assert worker.calls[-1] == ("refresh", KEY, manager.device_id)
    assert manager.token() != old
    assert stored()["token"] == manager.token()


def test_refresh_without_key_does_nothing(make_manager, worker):
    make_manager().refresh_now()
    assert worker.calls == []


def test_not_activated_reactivates_silently(make_manager, worker):
    manager = make_manager()
    manager.activate(KEY)
    worker.fail["refresh"] = LicenseRefused("not_activated")
    manager.refresh_now()
    assert worker.calls[-1][0] == "activate"
    assert manager.state() == "active"


def test_invalid_signature_reactivates_silently(make_manager, worker):
    manager = make_manager()
    manager.activate(KEY)
    data = stored()
    data["token"] = make_token(manager.device_id, kid="inconnu")
    write(data)
    manager = make_manager()
    worker.calls.clear()
    manager.refresh_now()
    assert [c[0] for c in worker.calls] == ["activate"]
    assert manager.state() == "active"


def test_reactivation_refused_is_unverified_with_message(make_manager, worker, clock):
    manager = make_manager()
    manager.activate(KEY)
    worker.fail["refresh"] = LicenseRefused("not_activated")
    worker.fail["activate"] = LicenseRefused("too_many_devices", devices=["A", "B"])
    clock.t = NOW + 8 * 86400
    manager.refresh_now()
    assert manager.state() == "unverified"
    assert "2 PC (A, B)" in manager.snapshot()["message"]


def test_thread_refreshes_at_start_and_periodically(make_manager, worker):
    manager = make_manager(interval=0.01)
    manager.activate(KEY)
    worker.calls.clear()
    manager.start()
    for _ in range(3):
        assert worker.refreshed.wait(2)
        worker.refreshed.clear()
    manager.stop()
    assert not manager.is_alive()
    assert sum(1 for c in worker.calls if c[0] == "refresh") >= 3


def test_thread_survives_unexpected_errors(make_manager, worker):
    manager = make_manager(interval=0.01)
    manager.activate(KEY)
    worker.fail["refresh"] = RuntimeError("bug")
    manager.start()
    assert worker.refreshed.wait(2)
    worker.refreshed.clear()
    assert worker.refreshed.wait(2)
    assert manager.is_alive()


# --- désactivation, portail, instantané ---


def test_deactivate_frees_the_place_and_forgets_the_key(make_manager, worker):
    manager = make_manager()
    manager.activate(KEY)
    device = manager.device_id
    manager.deactivate()
    assert worker.calls[-1] == ("deactivate", KEY, device)
    assert manager.state() == "none"
    assert "key" not in stored() and "token" not in stored()
    assert stored()["device_id"] == device


def test_deactivate_unreachable_keeps_the_license(make_manager, worker):
    manager = make_manager()
    manager.activate(KEY)
    worker.fail["deactivate"] = LicenseUnreachable()
    with pytest.raises(LicenseUnreachable):
        manager.deactivate()
    assert manager.state() == "active"


def test_portal_url_uses_the_token(make_manager, worker):
    manager = make_manager()
    manager.activate(KEY)
    assert manager.portal_url() == "https://billing.stripe.test/s"
    assert worker.calls[-1] == ("portal", manager.token())


def test_portal_without_token_raises(make_manager):
    with pytest.raises(LicenseError):
        make_manager().portal_url()


def test_snapshot(make_manager):
    manager = make_manager()
    assert manager.snapshot() == {
        "state": "none",
        "key_hint": None,
        "status": None,
        "period_end": None,
        "devices_max": 2,
        "message": None,
    }
    manager.activate(KEY)
    assert manager.snapshot() == {
        "state": "active",
        "key_hint": "VTO-…-PQRS",
        "status": "active",
        "period_end": NOW + 30 * 86400,
        "devices_max": 2,
        "message": None,
    }


# --- contournement de développement ---


def test_dev_bypass_outside_the_executable(make_manager, monkeypatch):
    monkeypatch.setenv("VTO_DEV_LICENSE", "1")
    manager = make_manager(frozen=lambda: False)
    assert manager.state() == "active"
    assert manager.licensed()


def test_dev_bypass_is_ignored_by_the_executable(make_manager, monkeypatch):
    monkeypatch.setenv("VTO_DEV_LICENSE", "1")
    assert make_manager(frozen=lambda: True).state() == "none"
