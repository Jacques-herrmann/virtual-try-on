"""Traduction des localisateurs de `vinted.json` (données) en localisateurs Playwright."""

import time
from collections.abc import Sequence

from vto.vinted.schema import CssLocator, LabelLocator, Locator, RoleLocator, TextLocator

POLL_MS = 100


class LocatorNotFound(Exception):
    """Aucune alternative visible ; `name` est le nom du localisateur dans `vinted.json`."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Localisateur introuvable : {name}")


def _fill(template: str, label: str | None) -> str:
    # Remplacement littéral : pas de str.format, la valeur n'est jamais interprétée.
    return template if label is None else template.replace("{label}", label)


def resolve(page, alt: Locator, label: str | None = None):
    match alt:
        case CssLocator(css=css):
            return page.locator(css)
        case LabelLocator(label=text):
            return page.get_by_label(_fill(text, label), exact=True)
        case TextLocator(text=text):
            return page.get_by_text(_fill(text, label), exact=True)
        case RoleLocator(role=role, name=name):
            return page.get_by_role(role, name=_fill(name, label), exact=True)
    raise TypeError(f"Forme de localisateur inconnue : {alt!r}")


def first_visible(
    page,
    name: str,
    alternatives: Sequence[Locator],
    *,
    timeout: float,
    label: str | None = None,
):
    """Premier élément visible parmi les alternatives, essayées dans l'ordre.

    Toutes sont réessayées jusqu'à `timeout` (ms) ; lève `LocatorNotFound(name)` sinon.
    """
    locators = [resolve(page, alt, label).first for alt in alternatives]
    deadline = time.monotonic() + timeout / 1000
    while True:
        for locator in locators:
            if locator.is_visible():
                return locator
        if time.monotonic() >= deadline:
            raise LocatorNotFound(name)
        page.wait_for_timeout(POLL_MS)


def first_present(
    page,
    name: str,
    alternatives: Sequence[Locator],
    *,
    timeout: float,
    label: str | None = None,
):
    """Comme `first_visible`, pour un élément présent mais caché (champ fichier, case stylée)."""
    locators = [resolve(page, alt, label) for alt in alternatives]
    deadline = time.monotonic() + timeout / 1000
    while True:
        for locator in locators:
            if locator.count():
                return locator.first
        if time.monotonic() >= deadline:
            raise LocatorNotFound(name)
        page.wait_for_timeout(POLL_MS)
