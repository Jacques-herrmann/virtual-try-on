import sys
import types
from pathlib import Path

import pytest

from vto import desktop, self_check
from vto.api import app as api_app

HAS_FRONT = (api_app.STATIC_DIR / "index.html").is_file()


@pytest.mark.skipif(not HAS_FRONT, reason="front non compilé (npm run build)")
def test_all_checks_pass_in_dev(tmp_path):
    out = tmp_path / "selfcheck.txt"
    assert self_check.run(out) == 0
    text = out.read_text(encoding="utf-8")
    names = ("modules", "interface", "tutoriel", "données Vinted", "scènes", "pilote Playwright")
    for name in names:
        assert f"OK  {name}" in text
    assert "ÉCHEC" not in text


def test_missing_resource_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(api_app, "STATIC_DIR", tmp_path / "absent")
    out = tmp_path / "selfcheck.txt"
    assert self_check.run(out) == 1
    assert "ÉCHEC interface" in out.read_text(encoding="utf-8")


def test_missing_tutorial_video_fails(tmp_path, monkeypatch):
    static = tmp_path / "static"
    (static / "tutorial").mkdir(parents=True)
    (static / "index.html").write_text("<html></html>", encoding="utf-8")
    (static / "tutorial" / "kaloe.vtt").write_text("WEBVTT", encoding="utf-8")
    monkeypatch.setattr(api_app, "STATIC_DIR", static)
    out = tmp_path / "selfcheck.txt"
    assert self_check.run(out) == 1
    text = out.read_text(encoding="utf-8")
    assert "OK  interface" in text and "ÉCHEC tutoriel" in text and "kaloe.mp4" in text


def test_empty_scene_pack_fails(tmp_path, monkeypatch):
    (tmp_path / "pack").mkdir()
    monkeypatch.setattr(self_check.scenes, "default_scenes_source", lambda: tmp_path / "pack")
    out = tmp_path / "selfcheck.txt"
    assert self_check.run(out) == 1
    assert "ÉCHEC scènes" in out.read_text(encoding="utf-8")


def test_missing_playwright_driver_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(
        self_check, "_driver_files", lambda: (Path(tmp_path / "node.exe"), Path("cli.js"))
    )
    out = tmp_path / "selfcheck.txt"
    assert self_check.run(out) == 1
    assert "ÉCHEC pilote Playwright" in out.read_text(encoding="utf-8")


def test_main_self_check_exits_with_its_code(data_dir, tmp_path, monkeypatch):
    # Ne jamais brancher le journal sur le vrai dossier de données (ni le garder ouvert).
    monkeypatch.setattr(desktop, "setup_logging", lambda **kw: None)
    calls = []
    monkeypatch.setattr(self_check, "run", lambda output: calls.append(output) or 3)
    with pytest.raises(SystemExit) as exc:
        desktop.main(["--self-check", "--output", str(tmp_path / "r.txt")])
    assert exc.value.code == 3
    assert calls == [tmp_path / "r.txt"]


def test_request_shutdown_destroys_windows(monkeypatch):
    destroyed = []
    window = types.SimpleNamespace(destroy=lambda: destroyed.append(True))
    monkeypatch.setitem(sys.modules, "webview", types.SimpleNamespace(windows=[window]))
    desktop.request_shutdown()
    assert destroyed == [True]


def test_request_shutdown_without_window(monkeypatch):
    monkeypatch.setitem(sys.modules, "webview", types.SimpleNamespace(windows=[]))
    desktop.request_shutdown()


def test_license_keys_check():
    from vto import self_check

    assert "k1" in self_check._license_keys()


def test_license_keys_check_fails_without_keys(monkeypatch):
    from vto import self_check
    from vto.licensing import token

    monkeypatch.setattr(token, "PUBLIC_KEYS", {})
    with pytest.raises(ValueError):
        self_check._license_keys()
