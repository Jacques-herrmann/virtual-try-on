"""Point d'entrée `vto-app` : API locale + fenêtre pywebview.

    vto-app          application complète
    vto-app --dev    API seule sur 127.0.0.1:8765 (jeton « dev »), pour `npm run dev`
    vto-app --self-check --output f   test de fumée de l'exécutable (code 0 si tout va bien)
"""

import argparse
import logging
import secrets
import socket
import threading
import time
import urllib.request
from pathlib import Path

import uvicorn

from vto import self_check
from vto.api.app import create_app
from vto.api.queue import GenerationQueue
from vto.api.security import LOGIN_PATH
from vto.core import scenes
from vto.core.logging import setup_logging
from vto.licensing.state import LicenseManager
from vto.updates.check import UpdateChecker
from vto.updates.install import Installer, clean_old_installers
from vto.vinted.worker import VintedWorker

log = logging.getLogger(__name__)

DEV_PORT = 8765
DEV_TOKEN = "dev"
STARTUP_TIMEOUT = 15.0


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def login_url(port: int, token: str) -> str:
    return f"http://127.0.0.1:{port}{LOGIN_PATH}?token={token}"


def _wait_until_ready(port: int, timeout: float = STARTUP_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def request_shutdown() -> None:
    """Ferme la fenêtre (appelé depuis un autre thread quand l'installeur est lancé).

    `main` reprend alors après `webview.start()` et arrête proprement le reste.
    """
    import webview

    for window in list(webview.windows):
        window.destroy()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="vto-app", description="Virtual Try-On")
    parser.add_argument("--dev", action="store_true", help="API seule, pour le serveur Vite")
    parser.add_argument("--self-check", action="store_true", help="test de fumée, puis quitte")
    parser.add_argument("--output", type=Path, help="fichier du rapport de --self-check")
    args = parser.parse_args(argv)

    setup_logging(console=args.dev)
    if args.self_check:
        raise SystemExit(self_check.run(args.output))
    scenes.ensure_default_scenes()
    # Le jeton enregistré suffit hors ligne ; le rafraîchissement se fait en arrière-plan.
    license_manager = LicenseManager()
    license_manager.start()
    queue = GenerationQueue(licensed=license_manager.licensed)
    queue.start()
    clean_old_installers()
    updates = UpdateChecker()
    updates.start()
    # Charge les données Vinted en arrière-plan : la fenêtre n'attend pas le réseau.
    vinted = VintedWorker(update_required=updates.is_required, licensed=license_manager.licensed)
    vinted.start()

    port = DEV_PORT if args.dev else find_free_port()
    token = DEV_TOKEN if args.dev else secrets.token_urlsafe(32)
    app = create_app(
        token=token,
        port=port,
        queue=queue,
        vinted_worker=vinted,
        update_checker=updates,
        installer=Installer(on_launched=request_shutdown),
    )
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None, access_log=False)
    )

    if args.dev:
        print(f"API prête. Interface : npm run dev, puis http://localhost:5173{LOGIN_PATH}"
              f"?token={DEV_TOKEN}")
        server.run()
        queue.stop()
        vinted.shutdown()
        updates.stop()
        license_manager.stop()
        return

    thread = threading.Thread(target=server.run, name="api", daemon=True)
    thread.start()
    if not _wait_until_ready(port):
        log.error("Le serveur local n'a pas démarré sur le port %s", port)
        raise SystemExit("Impossible de démarrer l'application. Consulte le fichier de log.")

    import webview  # import tardif : inutile en mode --dev et lent à charger

    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    webview.create_window(
        "Virtual Try-On", login_url(port, token), width=1280, height=800, min_size=(1024, 700)
    )
    webview.start()

    # Fenêtre fermée : l'article en cours sera repris au prochain lancement.
    queue.stop()
    vinted.shutdown()
    updates.stop()
    license_manager.stop()
    server.should_exit = True
    thread.join(timeout=5)


if __name__ == "__main__":
    main()
