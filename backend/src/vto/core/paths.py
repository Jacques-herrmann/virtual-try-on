"""Chemins des données utilisateur. Seul module à construire ces chemins."""

import os
from pathlib import Path

import platformdirs

APP_NAME = "VirtualTryOn"


def _ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    override = os.environ.get("VTO_DATA_DIR")
    root = Path(override) if override else Path(
        platformdirs.user_data_dir(APP_NAME, appauthor=False)
    )
    return _ensure(root)


def settings_file() -> Path:
    return data_dir() / "settings.json"


def scenes_dir() -> Path:
    return _ensure(data_dir() / "scenes")


def articles_dir() -> Path:
    return _ensure(data_dir() / "articles")


def article_dir(article_id: str) -> Path:
    return articles_dir() / article_id


def logs_dir() -> Path:
    return _ensure(data_dir() / "logs")


def browser_profile_dir() -> Path:
    return _ensure(data_dir() / "browser-profile")


def cache_dir() -> Path:
    return _ensure(data_dir() / "cache")


def vinted_log_dir() -> Path:
    return _ensure(logs_dir() / "vinted")


def safe_join(base: Path, rel: str) -> Path | None:
    """`base / rel` résolu, ou None si `rel` est vide, absolu ou sort de `base`."""
    if not rel or Path(rel).is_absolute() or Path(rel).drive or rel.startswith(("/", "\\")):
        return None
    root = base.resolve()
    target = (root / rel).resolve()
    if target == root or not target.is_relative_to(root):
        return None
    return target
