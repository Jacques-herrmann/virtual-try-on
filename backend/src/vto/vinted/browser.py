"""Navigateur dédié à Vinted : Chrome installé (sinon Edge) avec un profil persistant.

Le navigateur est lancé comme par le vendeur (`chrome.exe --user-data-dir=…`), puis piloté
par le protocole de débogage. Lancé par Playwright, il porte les marques de l'automatisation
(`navigator.webdriver`) et l'anti-robots de Vinted refuse la connexion.

Le vendeur se connecte lui-même une fois ; aucun identifiant n'est stocké par l'app.
"""

import logging
import os
import shutil
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

from vto.core import paths
from vto.core.errors import VtoError
from vto.vinted.locators import LocatorNotFound, first_visible
from vto.vinted.schema import VintedData

log = logging.getLogger(__name__)

CHANNELS = ("chrome", "msedge")
LOGIN_CHECK_MS = 3000
STARTUP_TIMEOUT = 20.0  # s
CLOSE_TIMEOUT = 5.0  # s

# Emplacements d'installation sous Windows, relatifs aux dossiers de programmes.
_LOCATIONS = {
    "chrome": ("Google/Chrome/Application/chrome.exe",),
    "msedge": ("Microsoft/Edge/Application/msedge.exe",),
}
_ROOTS = ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
# Noms dans le PATH (développement et CI sous Linux).
_COMMANDS = {
    "chrome": ("chrome", "google-chrome", "google-chrome-stable"),
    "msedge": ("msedge", "microsoft-edge", "microsoft-edge-stable"),
}

LAUNCH_ARGS = (
    "--no-first-run",
    "--no-default-browser-check",
    "--start-maximized",
)


class BrowserMissing(VtoError):
    user_message = (
        "Ni Google Chrome ni Microsoft Edge n'est installé sur cet ordinateur. "
        "Installe Google Chrome pour envoyer tes annonces sur Vinted."
    )


class ProfileInUse(VtoError):
    user_message = "La fenêtre Vinted est déjà ouverte. Ferme-la, puis réessaie."


class BrowserStartFailed(VtoError):
    user_message = "La fenêtre Vinted n'a pas pu s'ouvrir. Réessaie dans quelques instants."


def find_executable(channel: str) -> str | None:
    for root_var in _ROOTS:
        root = os.environ.get(root_var)
        if not root:
            continue
        for relative in _LOCATIONS[channel]:
            candidate = Path(root) / relative
            if candidate.is_file():
                return str(candidate)
    for command in _COMMANDS[channel]:
        found = shutil.which(command)
        if found:
            return found
    return None


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_port(port: int, process: subprocess.Popen, timeout: float) -> bool:
    """Vrai quand le port de débogage répond ; faux si le processus s'arrête ou au délai."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1):
                return True
        except OSError:
            time.sleep(0.2)
    return False


class BrowserSession:
    """Navigateur lancé par l'app ; s'utilise comme un contexte Playwright."""

    def __init__(self, process: subprocess.Popen, browser):
        self.process = process
        self.browser = browser
        self.context = browser.contexts[0]

    @property
    def pages(self):
        return self.context.pages

    def new_page(self):
        return self.context.new_page()

    def close(self) -> None:
        """Ferme le navigateur proprement, puis de force s'il ne répond pas."""
        try:
            self.browser.new_browser_cdp_session().send("Browser.close")
        except Exception:
            log.debug("Fermeture du navigateur par le protocole", exc_info=True)
        try:
            self.process.wait(timeout=CLOSE_TIMEOUT)
        except subprocess.TimeoutExpired:
            self.process.kill()


def open_context(playwright, *, extra_args: tuple[str, ...] | list[str] = ()) -> BrowserSession:
    """Lance Chrome (sinon Edge) sur le profil dédié et s'y connecte."""
    executable = next(
        (exe for exe in (find_executable(c) for c in CHANNELS) if exe), None
    )
    if executable is None:
        raise BrowserMissing()

    port = free_port()
    args = [
        executable,
        f"--user-data-dir={paths.browser_profile_dir()}",
        f"--remote-debugging-port={port}",
        *LAUNCH_ARGS,
        *extra_args,
    ]
    process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not _wait_for_port(port, process, STARTUP_TIMEOUT):
        if process.poll() is not None:
            # Profil déjà ouvert : le navigateur confie l'ouverture à l'instance existante
            # et quitte aussitôt, sans ouvrir de port de débogage.
            log.warning("Profil navigateur déjà utilisé (%s a quitté aussitôt)", executable)
            raise ProfileInUse()
        process.kill()
        log.error("Le port de débogage de %s n'a pas répondu", executable)
        raise BrowserStartFailed()

    log.info("Navigateur lancé : %s (port %s)", executable, port)
    browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", no_defaults=True)
    return BrowserSession(process, browser)


def is_logged_in(page, data: VintedData, *, timeout: float = LOGIN_CHECK_MS) -> bool:
    if not page.url.startswith(data.urls.home):
        # Vinted n'émet pas toujours l'événement « load » : on n'attend que le document.
        page.goto(data.urls.home, wait_until="domcontentloaded")
    try:
        first_visible(page, "logged_in", data.locators["logged_in"], timeout=timeout)
    except LocatorNotFound:
        return False
    return True
