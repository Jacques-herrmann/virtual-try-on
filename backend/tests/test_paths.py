from pathlib import Path

import platformdirs

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
    assert paths.scenes_dir() == data_dir / "scenes"
    assert paths.articles_dir() == data_dir / "articles"
    assert paths.article_dir("abc") == data_dir / "articles" / "abc"
    assert paths.logs_dir() == data_dir / "logs"


def test_directories_are_created_on_demand(data_dir):
    for d in (paths.scenes_dir(), paths.articles_dir(), paths.logs_dir()):
        assert d.is_dir()
