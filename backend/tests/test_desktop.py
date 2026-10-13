import socket

import pytest

from vto import desktop


def test_find_free_port_is_bindable():
    port = desktop.find_free_port()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))


def test_login_url():
    assert desktop.login_url(5000, "abc") == "http://127.0.0.1:5000/api/session?token=abc"


class _Stop(Exception):
    pass


def test_main_migrates_data_before_logging(monkeypatch):
    calls = []
    monkeypatch.setattr(
        desktop.paths, "migrate_legacy_data_dir", lambda: calls.append("migrate") or "ok"
    )

    def logging_then_stop(console=False):
        calls.append("logging")
        raise _Stop

    monkeypatch.setattr(desktop, "setup_logging", logging_then_stop)
    with pytest.raises(_Stop):
        desktop.main([])
    assert calls == ["migrate", "logging"]


def test_self_check_does_not_migrate(monkeypatch):
    calls = []
    monkeypatch.setattr(desktop.paths, "migrate_legacy_data_dir", lambda: calls.append("migrate"))
    monkeypatch.setattr(desktop, "setup_logging", lambda console=False: None)
    monkeypatch.setattr(desktop.self_check, "run", lambda output: 0)
    with pytest.raises(SystemExit):
        desktop.main(["--self-check"])
    assert calls == []
