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
