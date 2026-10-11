"""Navigateur dédié à Vinted : Chrome installé (sinon Edge) avec un profil persistant.

Le vendeur se connecte lui-même une fois ; aucun identifiant n'est stocké par l'app.
"""

import logging

from playwright.sync_api import Error

from vto.core import paths
from vto.core.errors import VtoError
from vto.vinted.locators import LocatorNotFound, first_visible
from vto.vinted.schema import VintedData

log = logging.getLogger(__name__)

CHANNELS = ("chrome", "msedge")
LOGIN_CHECK_MS = 3000


class BrowserMissing(VtoError):
    user_message = (
        "Ni Google Chrome ni Microsoft Edge n'est installé sur cet ordinateur. "
        "Installe Google Chrome pour envoyer tes annonces sur Vinted."
    )


class ProfileInUse(VtoError):
    user_message = "La fenêtre Vinted est déjà ouverte. Ferme-la, puis réessaie."


def _is_missing(exc: Error) -> bool:
    return "Chromium distribution" in str(exc) and "is not found" in str(exc)


def _is_profile_locked(exc: Error) -> bool:
    # Profil déjà ouvert : Chrome confie l'ouverture à l'instance existante et quitte
    # aussitôt ; Playwright ne voit qu'un navigateur fermé pendant le lancement.
    return "Target page, context or browser has been closed" in str(exc)


def open_context(playwright):
    """Contexte persistant sur le profil dédié ; fenêtre visible, maximisée, en français."""
    profile = str(paths.browser_profile_dir())
    for channel in CHANNELS:
        try:
            return playwright.chromium.launch_persistent_context(
                profile,
                channel=channel,
                headless=False,
                locale="fr-FR",
                no_viewport=True,
                args=["--start-maximized"],
            )
        except Error as exc:
            if _is_missing(exc):
                log.info("Navigateur %s absent", channel)
                continue
            if _is_profile_locked(exc):
                log.warning("Profil navigateur déjà utilisé : %s", str(exc).splitlines()[0])
                raise ProfileInUse() from exc
            raise
    raise BrowserMissing()


def is_logged_in(page, data: VintedData, *, timeout: float = LOGIN_CHECK_MS) -> bool:
    if not page.url.startswith(data.urls.home):
        page.goto(data.urls.home)
    try:
        first_visible(page, "logged_in", data.locators["logged_in"], timeout=timeout)
    except LocatorNotFound:
        return False
    return True
