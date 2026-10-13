from pathlib import Path

import platformdirs
import pytest

from vto.core import paths


def test_data_dir_uses_env_override(data_dir):
    assert paths.data_dir() == data_dir
    assert data_dir.is_dir()


def test_data_dir_defaults_to_platform_dir(monkeypatch):
    monkeypatch.delenv("VTO_DATA_DIR", raising=False)
    expected = Path(platformdirs.user_data_dir("VirtualTryOn", appauthor=False))
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: None)
    assert paths.data_dir() == expected


def test_sub_paths_are_under_data_dir(data_dir):
    assert paths.settings_file() == data_dir / "settings.json"
    assert paths.license_file() == data_dir / "license.json"
    assert paths.scenes_dir() == data_dir / "scenes"
    assert paths.articles_dir() == data_dir / "articles"
    assert paths.article_dir("abc") == data_dir / "articles" / "abc"
    assert paths.logs_dir() == data_dir / "logs"


def test_directories_are_created_on_demand(data_dir):
    for d in (paths.scenes_dir(), paths.articles_dir(), paths.logs_dir()):
        assert d.is_dir()


def test_safe_join_inside(tmp_path):
    assert paths.safe_join(tmp_path, "a/b.jpg") == (tmp_path / "a" / "b.jpg").resolve()


@pytest.mark.parametrize("rel", ["../x", "a/../../x", "", ".", "C:/Windows", "/etc/passwd"])
def test_safe_join_refuses_escape(tmp_path, rel):
    assert paths.safe_join(tmp_path, rel) is None


def test_vinted_paths_are_under_data_dir(data_dir):
    assert paths.browser_profile_dir() == data_dir / "browser-profile"
    assert paths.cache_dir() == data_dir / "cache"
    assert paths.vinted_log_dir() == data_dir / "logs" / "vinted"


def test_vinted_directories_are_created_on_demand(data_dir):
    for d in (paths.browser_profile_dir(), paths.cache_dir(), paths.vinted_log_dir()):
        assert d.is_dir()


def test_is_frozen_follows_pyinstaller_flag(monkeypatch):
    assert paths.is_frozen() is False
    monkeypatch.setattr("sys.frozen", True, raising=False)
    assert paths.is_frozen() is True


def test_updates_cache_dir_is_created_under_cache(data_dir):
    assert paths.updates_cache_dir() == data_dir / "cache" / "updates"
    assert paths.updates_cache_dir().is_dir()
