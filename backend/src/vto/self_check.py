"""Test de fumée de l'exécutable : `Kaloe.exe --self-check --output f`.

Vérifie que PyInstaller a tout embarqué (modules et données), sans fenêtre ni réseau.
"""

import base64
import importlib
import logging
import pkgutil
import sys
from collections.abc import Callable
from pathlib import Path

import vto
from vto.api import app as api_app
from vto.core import scenes
from vto.vinted import remote
from vto.vinted.schema import VintedData

log = logging.getLogger(__name__)


def _modules() -> str:
    names = [m.name for m in pkgutil.walk_packages(vto.__path__, prefix="vto.")]
    for name in names:
        importlib.import_module(name)
    return f"{len(names)} modules"


def _window() -> str:
    # pywebview charge pythonnet (WinForms + WebView2) seulement sous Windows.
    importlib.import_module("webview")
    if sys.platform == "win32":
        importlib.import_module("webview.platforms.winforms")
    return "pywebview"


def _front() -> str:
    index = api_app.STATIC_DIR / "index.html"
    if not index.is_file():
        raise FileNotFoundError(index)
    return str(api_app.STATIC_DIR)


def _vinted_data() -> str:
    return f"révision {VintedData.model_validate_json(remote.bundled_text()).revision}"


def _license_keys() -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    from vto.licensing import token

    if not token.PUBLIC_KEYS:
        raise ValueError("aucune clé publique de licence")
    for raw in token.PUBLIC_KEYS.values():
        Ed25519PublicKey.from_public_bytes(base64.b64decode(raw))
    return ", ".join(sorted(token.PUBLIC_KEYS))


def _scenes() -> str:
    source = scenes.default_scenes_source()
    found = [d.name for d in source.iterdir() if (d / "prompt.md").is_file()] if (
        source.is_dir()
    ) else []
    if not found:
        raise FileNotFoundError(f"aucune scène dans {source}")
    return ", ".join(sorted(found))


def _driver_files() -> tuple[Path, ...]:
    from playwright._impl._driver import compute_driver_executable

    return tuple(Path(p) for p in compute_driver_executable())


def _playwright() -> str:
    files = _driver_files()
    missing = [str(p) for p in files if not p.is_file()]
    if missing:
        raise FileNotFoundError(", ".join(missing))
    return str(files[0].parent)


CHECKS: list[tuple[str, Callable[[], str]]] = [
    ("modules", _modules),
    ("fenêtre", _window),
    ("interface", _front),
    ("données Vinted", _vinted_data),
    ("scènes", _scenes),
    ("clés de licence", _license_keys),
    ("pilote Playwright", _playwright),
]


def run(output: Path | None = None) -> int:
    lines = [f"Kaloé {vto.__version__}"]
    failed = False
    for name, check in CHECKS:
        try:
            lines.append(f"OK  {name} : {check()}")
        except Exception as exc:
            failed = True
            lines.append(f"ÉCHEC {name} : {type(exc).__name__} {exc}")
    report = "\n".join(lines) + "\n"
    log.info("Auto-vérification :\n%s", report)
    if output is not None:
        output.write_text(report, encoding="utf-8")
    return 1 if failed else 0
