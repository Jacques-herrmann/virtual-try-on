"""Chemins des données utilisateur. Seul module à construire ces chemins."""

import os
import re
import sys
from pathlib import Path

import platformdirs

APP_NAME = "Kaloe"
# Nom d'avant le sous-projet 6 : son dossier de données est déplacé au premier lancement.
LEGACY_APP_NAME = "VirtualTryOn"


def _ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _platform_dir(name: str) -> Path:
    return Path(platformdirs.user_data_dir(name, appauthor=False))


def data_dir() -> Path:
    override = os.environ.get("VTO_DATA_DIR")
    if override:
        return _ensure(Path(override))
    root = _platform_dir(APP_NAME)
    legacy = _platform_dir(LEGACY_APP_NAME)
    # Migration pas encore faite (ou ratée) : on reste sur l'ancien dossier.
    if not root.exists() and legacy.exists():
        return legacy
    return _ensure(root)


def migrate_legacy_data_dir() -> str:
    """Déplace `%LOCALAPPDATA%\\VirtualTryOn` vers `%LOCALAPPDATA%\\Kaloe` s'il y a lieu.

    Un simple renommage (même volume) : ni copie ni suppression. En cas d'échec
    (fichier verrouillé), `data_dir()` continue sur l'ancien dossier et l'app
    retente au lancement suivant. Ne lève jamais ; rend une phrase pour le log.
    """
    if os.environ.get("VTO_DATA_DIR"):
        return "VTO_DATA_DIR défini : rien à migrer"
    root = _platform_dir(APP_NAME)
    legacy = _platform_dir(LEGACY_APP_NAME)
    if not legacy.exists():
        return "rien à migrer"
    if root.exists():
        return f"{root} existe déjà : {legacy} laissé en place"
    try:
        os.rename(legacy, root)
    except OSError as exc:
        return f"déplacement de {legacy} vers {root} impossible ({exc}) : ancien dossier conservé"
    return f"données déplacées de {legacy} vers {root}"


def settings_file() -> Path:
    return data_dir() / "settings.json"


def license_file() -> Path:
    """Clé de licence, identifiant du PC et jeton : jamais effacé implicitement."""
    return data_dir() / "license.json"


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


def updates_cache_dir() -> Path:
    """Installeurs téléchargés par l'app : jamais des données du client."""
    return _ensure(cache_dir() / "updates")


def vinted_log_dir() -> Path:
    return _ensure(logs_dir() / "vinted")


def is_frozen() -> bool:
    """Vrai dans l'exécutable PyInstaller (app installée), faux en développement."""
    return bool(getattr(sys, "frozen", False))


def safe_join(base: Path, rel: str) -> Path | None:
    """`base / rel` résolu, ou None si `rel` est vide, absolu ou sort de `base`."""
    if not rel or Path(rel).is_absolute() or Path(rel).drive or rel.startswith(("/", "\\")):
        return None
    if re.match(r"[A-Za-z]:", rel):  # lecteur Windows, refusé aussi hors Windows
        return None
    root = base.resolve()
    target = (root / rel).resolve()
    if target == root or not target.is_relative_to(root):
        return None
    return target
