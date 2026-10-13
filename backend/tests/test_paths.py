from pathlib import Path

import platformdirs
import pytest

from vto.core import paths


def test_data_dir_uses_env_override(data_dir):
    assert paths.data_dir() == data_dir
    assert data_dir.is_dir()


def test_data_dir_defaults_to_platform_dir(monkeypatch):
    monkeypatch.delenv("VTO_DATA_DIR", raising=False)
    expected = Path(platformdirs.user_data_dir("Kaloe", appauthor=False))
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: None)
    monkeypatch.setattr(Path, "exists", lambda self: self == expected)
    assert paths.data_dir() == expected


@pytest.fixture
def platform_root(tmp_path, monkeypatch) -> Path:
    """Dossier parent des données (%LOCALAPPDATA%), sans VTO_DATA_DIR."""
    monkeypatch.delenv("VTO_DATA_DIR", raising=False)
    monkeypatch.setattr(
        paths.platformdirs, "user_data_dir", lambda name, appauthor=None: str(tmp_path / name)
    )
    return tmp_path


def _fill_legacy(root: Path) -> Path:
    old = root / "VirtualTryOn"
    (old / "articles" / "a1").mkdir(parents=True)
    (old / "articles" / "a1" / "article.json").write_text("{}", encoding="utf-8")
    (old / "license.json").write_text('{"key": "K"}', encoding="utf-8")
    (old / "browser-profile" / "Default").mkdir(parents=True)
    (old / "browser-profile" / "Default" / "Cookies").write_bytes(b"session")
    return old


def test_migration_without_legacy_folder_does_nothing(platform_root):
    assert "rien" in paths.migrate_legacy_data_dir()
    assert not (platform_root / "Kaloe").exists()
    assert paths.data_dir() == platform_root / "Kaloe"


def test_migration_moves_legacy_folder(platform_root):
    old = _fill_legacy(platform_root)
    new = platform_root / "Kaloe"

    assert "déplacées" in paths.migrate_legacy_data_dir()

    assert not old.exists()
    assert (new / "articles" / "a1" / "article.json").read_text(encoding="utf-8") == "{}"
    assert (new / "license.json").read_text(encoding="utf-8") == '{"key": "K"}'
    assert (new / "browser-profile" / "Default" / "Cookies").read_bytes() == b"session"
    assert paths.data_dir() == new


def test_migration_leaves_both_folders_when_new_exists(platform_root):
    old = _fill_legacy(platform_root)
    (platform_root / "Kaloe").mkdir()

    paths.migrate_legacy_data_dir()

    assert (old / "license.json").exists()
    assert paths.data_dir() == platform_root / "Kaloe"


def test_failed_migration_keeps_using_legacy_folder(platform_root, monkeypatch):
    old = _fill_legacy(platform_root)

    def locked(src, dst):
        raise PermissionError("fichier verrouillé")

    monkeypatch.setattr(paths.os, "rename", locked)

    assert "impossible" in paths.migrate_legacy_data_dir()
    assert paths.data_dir() == old
    assert (old / "license.json").exists()
    assert not (platform_root / "Kaloe").exists()


def test_env_override_disables_migration(platform_root, monkeypatch):
    old = _fill_legacy(platform_root)
    monkeypatch.setenv("VTO_DATA_DIR", str(platform_root / "custom"))

    paths.migrate_legacy_data_dir()

    assert (old / "license.json").exists()
    assert paths.data_dir() == platform_root / "custom"


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
