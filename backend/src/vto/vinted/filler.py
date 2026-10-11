"""Remplissage du formulaire « Vends ton article » de vinted.fr.

Chaque champ est rempli indépendamment : un échec est journalisé (avec une capture d'écran)
et le champ est signalé « à compléter », sans arrêter les autres. Seuls l'ouverture de la
page, l'envoi des photos et l'enregistrement font échouer l'article.
"""

import logging
import random
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from vto.core import paths, storage
from vto.core.models import Article
from vto.vinted.catalog import Catalog
from vto.vinted.locators import LocatorNotFound, first_present, first_visible, resolve
from vto.vinted.schema import VintedData

log = logging.getLogger(__name__)

Mode = Literal["draft", "publish"]

PAGE_ERROR = "Vinted ne répond pas. Réessaie plus tard."
PHOTOS_ERROR = "Les photos n'ont pas pu être envoyées sur Vinted."
SAVE_ERROR = "L'annonce n'a pas pu être enregistrée sur Vinted."

MAX_CATEGORY_DEPTH = 8

# Préfixes des onglets de tailles (« FR 38 » se trouve sous l'onglet « FR »).
SIZE_TABS = ("EU", "UK", "FR", "IT", "US")


@dataclass
class FillReport:
    mode: Mode  # action réellement effectuée
    status: Literal["ok", "partial", "error"]
    missing_fields: list[str] = field(default_factory=list)
    url: str | None = None
    error: str | None = None  # message client, en français


@dataclass(frozen=True)
class Timing:
    """Délais en millisecondes ; les tests les réduisent."""

    page: float = 30_000
    step: float = 10_000
    optional: float = 2_000  # éléments qui peuvent ne pas exister (cookies, pop-up)
    photos: float = 30_000
    save: float = 20_000
    pause: tuple[float, float] = (300, 900)  # entre deux actions, comme une personne


class MissingField(Exception):
    """Champ non rempli ; `label` est le libellé montré au vendeur."""

    def __init__(self, label: str, reason: str):
        self.label = label
        super().__init__(reason)


def format_price(price: float) -> str:
    return f"{price:.2f}".replace(".", ",")


def normalize(text: str) -> str:
    """Pour comparer des libellés sans tenir compte de la casse ni des accents."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()


def same_spaces(text: str) -> str:
    """Vinted écrit « FR 38 » avec une espace insécable."""
    return " ".join(text.split())


def size_tab(size: str) -> str | None:
    parts = same_spaces(size).split(" ", 1)
    return parts[0] if len(parts) == 2 and parts[0] in SIZE_TABS else None


class _Filler:
    def __init__(self, page, article: Article, data: VintedData, catalog: Catalog, timing: Timing):
        self.page = page
        self.article = article
        self.data = data
        self.catalog = catalog
        self.timing = timing
        self.listing = article.listing
        self.missing: list[str] = []
        self._cdp = None

    # --- Outils ---------------------------------------------------------------------------

    def pause(self) -> None:
        low, high = self.timing.pause
        if high > 0:
            self.page.wait_for_timeout(random.uniform(low, high))

    def find(self, name: str, *, label: str | None = None, timeout: float | None = None):
        return first_visible(
            self.page, name, self.data.locators[name],
            timeout=self.timing.step if timeout is None else timeout, label=label,
        )

    def click(self, locator) -> None:
        locator.scroll_into_view_if_needed()
        try:
            locator.click(timeout=self.timing.step)
        except Exception:
            log.debug("Clic intercepté", exc_info=True)
            if self.close_popups():
                locator.click(timeout=self.timing.step)
            else:
                # En-tête collant ou animation par-dessus : le clic est envoyé à l'élément.
                locator.dispatch_event("click")
        self.pause()

    def open_list(self, name: str) -> None:
        self.click(self.find(name))

    def screenshot(self, label: str) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = paths.vinted_log_dir() / f"{stamp}-{self.article.id}-{normalize(label)}.png"
        try:
            self.page.screenshot(path=str(target), full_page=True)
        except Exception:
            log.debug("Capture impossible", exc_info=True)

    def restore_window(self) -> None:
        """Une fenêtre réduite n'est plus dessinée : clics et défilements y restent bloqués.
        Si le vendeur l'a réduite pendant l'envoi, on la remet à l'écran."""
        try:
            if self._cdp is None:
                self._cdp = self.page.context.new_cdp_session(self.page)
            window = self._cdp.send("Browser.getWindowForTarget")
            if window["bounds"].get("windowState") != "minimized":
                return
            self._cdp.send(
                "Browser.setWindowBounds",
                {"windowId": window["windowId"], "bounds": {"windowState": "normal"}},
            )
            self.page.bring_to_front()
            log.info("Vinted, article %s : fenêtre réduite remise à l'écran", self.article.id)
        except Exception as exc:
            if "has been closed" in str(exc):
                raise
            log.debug("État de la fenêtre illisible", exc_info=True)

    def close_popups(self) -> bool:
        """Ferme une fenêtre qui recouvre le formulaire (« Preuves d'authenticité » s'ouvre
        après le choix de certaines marques) ; on ne cherche le bouton que dans la fenêtre."""
        dialogs = self.page.locator("[aria-modal='true']")
        if not dialogs.count():
            return False
        try:
            button = first_visible(
                dialogs, "popup_close", self.data.locators["popup_close"], timeout=0
            )
        except LocatorNotFound:
            return False
        log.info("Vinted, article %s : fenêtre fermée", self.article.id)
        button.click(timeout=self.timing.step)
        self.pause()
        return True

    def step(self, label: str, action) -> None:
        """Exécute une étape ; tout échec rend le champ « à compléter »."""
        try:
            self.restore_window()
            self.close_popups()
            action()
        except MissingField as exc:
            self.mark_missing(exc.label, str(exc))
        except LocatorNotFound as exc:
            self.mark_missing(label, f"localisateur introuvable : {exc.name}")
        except Exception as exc:
            if "has been closed" in str(exc):
                raise
            self.mark_missing(label, f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}")

    def mark_missing(self, label: str, reason: str) -> None:
        log.warning(
            "Vinted, article %s : « %s » à compléter (%s ; données %s)",
            self.article.id, label, reason, self.data.revision,
        )
        if label not in self.missing:
            self.missing.append(label)
        self.screenshot(label)

    # --- Étapes ---------------------------------------------------------------------------

    def open_page(self) -> bool:
        try:
            self.page.goto(self.data.urls.new_item, wait_until="domcontentloaded")
            self.find("title", timeout=self.timing.page)
        except Exception as exc:
            if "has been closed" in str(exc):
                raise
            log.warning("Formulaire Vinted non chargé : %s", str(exc).splitlines()[0][:200])
            return False
        for name in ("cookie_accept", "popup_close"):
            try:
                self.click(self.find(name, timeout=self.timing.optional))
            except LocatorNotFound:
                pass
        return True

    def photos(self) -> bool:
        self.restore_window()
        gallery = storage.effective_gallery(self.article)
        if not gallery:
            log.warning("Article %s : aucune photo à envoyer", self.article.id)
            return False
        folder = paths.article_dir(self.article.id)
        try:
            field_ = first_present(
                self.page, "photo_input", self.data.locators["photo_input"],
                timeout=self.timing.step,
            )
            field_.set_input_files([str(folder / p) for p in gallery])
            deadline = time.monotonic() + self.timing.photos / 1000
            thumbs = [resolve(self.page, alt) for alt in self.data.locators["photo_thumb"]]
            while max(t.count() for t in thumbs) < len(gallery):
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"{len(gallery)} miniatures attendues")
                self.page.wait_for_timeout(250)
        except Exception as exc:
            if "has been closed" in str(exc):
                raise
            log.warning("Photos non envoyées : %s", str(exc).splitlines()[0][:200])
            return False
        if any(p.startswith("generated/") for p in gallery):
            self.step("Mention IA", self.mark_ai)
        return True

    def mark_ai(self) -> None:
        box = first_present(
            self.page, "ai_photo", self.data.locators["ai_photo"], timeout=self.timing.step
        )
        box.check(force=True)
        if not box.is_checked():
            raise MissingField("Mention IA", "case non cochée")

    def text(self, name: str, label: str, value: str | None) -> None:
        if not value or not value.strip():
            raise MissingField(label, "vide")
        box = self.find(name)
        box.fill(value)
        self.pause()

    def category(self) -> None:
        path = self.catalog.path(self.listing.category)
        if not path or not self.catalog.is_leaf(self.listing.category):
            raise MissingField("Catégorie", f"catégorie inconnue : {self.listing.category!r}")
        self.open_list("category_open")
        self._category_root(path[0])
        for label in path:
            self.click(self.find("category_option", label=label))

    def _category_root(self, root: str) -> None:
        """Vinted présélectionne une catégorie d'après les photos : la liste s'ouvre alors à
        son niveau. On remonte jusqu'à voir la racine voulue."""
        for _ in range(MAX_CATEGORY_DEPTH):
            try:
                self.find("category_option", label=root, timeout=self.timing.optional)
                return
            except LocatorNotFound:
                self.click(self.find("category_back", timeout=self.timing.optional))
        raise LocatorNotFound("category_option")

    def brand(self) -> None:
        brand = (self.listing.brand or "").strip()
        if not brand:
            raise MissingField("Marque", "vide")
        self.open_list("brand_open")
        try:
            search = self.find("brand_input", timeout=self.timing.optional)
        except LocatorNotFound:
            # Il arrive que le premier clic ne fasse que donner le focus au champ.
            log.info("Vinted, article %s : liste des marques rouverte", self.article.id)
            self.open_list("brand_open")
            search = self.find("brand_input")
        search.fill("")
        search.press_sequentially(brand, delay=60)
        self.page.wait_for_timeout(min(1500, self.timing.step))
        try:
            option = self.find("brand_option", label=brand, timeout=self.timing.optional)
        except LocatorNotFound:
            option = self._brand_ignoring_case(brand)
        self.click(option)

    def _brand_ignoring_case(self, brand: str):
        wanted = normalize(brand)
        for alt in self.data.locators["brand_options"]:
            for option in resolve(self.page, alt).all():
                name = option.get_attribute("aria-label") or option.inner_text()
                if normalize(name) == wanted:
                    return option
        self.open_list("brand_open")  # referme la liste
        raise MissingField("Marque", f"aucune suggestion identique à {brand!r}")

    def size(self) -> None:
        grid = self.catalog.sizes(self.listing.category)
        if not grid:
            return  # catégorie sans taille
        wanted = same_spaces(self.listing.size or "")
        size = next((label for label in grid if same_spaces(label) == wanted), None)
        if not wanted or size is None:
            raise MissingField("Taille", f"{self.listing.size!r} absente de la grille")
        self.open_list("size_open")
        try:
            option = self.find("size_option", label=size, timeout=self.timing.optional)
        except LocatorNotFound:
            tab = size_tab(size)
            if tab is None:
                raise
            self.click(self.find("size_tab", label=tab))
            option = self.find("size_option", label=size)
        self.click(option)

    def condition(self) -> None:
        condition = self.listing.condition
        label = self.data.conditions.get(condition) if condition else None
        if not label:
            raise MissingField("État", f"{condition!r} sans libellé Vinted")
        self.open_list("condition_open")
        self.click(self.find("condition_option", label=label))

    def colors(self) -> None:
        colors = self.listing.color
        if not colors:
            return
        unknown = [c for c in colors if c not in self.data.colors]
        known = [c for c in colors if c in self.data.colors]
        if known:
            self.open_list("color_open")
            for color in known:
                self.click(self.find("color_option", label=color))
            self.click(self.find("color_close"))
        if unknown:
            raise MissingField("Couleur", f"inconnues sur Vinted : {unknown}")

    def price(self) -> None:
        if self.listing.price is None:
            raise MissingField("Prix", "vide")
        box = self.find("price")
        box.fill(format_price(self.listing.price))
        self.pause()

    def parcel(self) -> None:
        parcel = self.listing.parcel_size
        if not parcel:
            return  # Vinted propose une taille par défaut
        label = self.data.parcel_sizes.get(parcel)
        if not label:
            raise MissingField("Taille du colis", f"{parcel!r} sans libellé Vinted")
        self.click(self.find("parcel_option", label=label))

    def save(self, mode: Mode) -> str | None:
        """Enregistre ; renvoie l'URL obtenue, ou None si l'enregistrement a échoué."""
        start_url = self.page.url
        button = "publish" if mode == "publish" else "save_draft"
        try:
            self.restore_window()
            self.close_popups()
            self.click(self.find(button))
            deadline = time.monotonic() + self.timing.save / 1000
            while True:
                try:
                    self.find("saved_marker", timeout=0)
                    break
                except LocatorNotFound:
                    pass
                if self.page.url != start_url and mode == "publish":
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError("enregistrement non confirmé")
                self.page.wait_for_timeout(250)
        except Exception as exc:
            if "has been closed" in str(exc):
                raise
            log.warning("Enregistrement Vinted non confirmé : %s", str(exc).splitlines()[0][:200])
            self.screenshot("enregistrement")
            return None
        return self.draft_url() if mode == "draft" else self.page.url

    def draft_url(self) -> str:
        """Lien du brouillon sur le profil (titre de l'annonce), sinon l'adresse courante.

        Les annonces du profil s'affichent après le nom : on les attend un moment.
        """
        title = normalize(self.listing.title)
        deadline = time.monotonic() + self.timing.step / 1000
        while True:
            for alt in self.data.locators["draft_link"]:
                for link in resolve(self.page, alt).all():
                    if normalize(link.get_attribute("title") or "").startswith(title):
                        href = link.get_attribute("href") or ""
                        if href.startswith("/"):
                            return f"{self.data.urls.home.rstrip('/')}{href}"
                        return href
            if time.monotonic() >= deadline:
                log.warning("Lien du brouillon introuvable sur le profil")
                return self.page.url
            self.page.wait_for_timeout(250)


def fill_item(
    page,
    article: Article,
    data: VintedData,
    catalog: Catalog,
    mode: Mode,
    *,
    timing: Timing | None = None,
) -> FillReport:
    filler = _Filler(page, article, data, catalog, timing or Timing())
    if article.listing is None:
        return FillReport(mode="draft", status="error", error=SAVE_ERROR)
    if not filler.open_page():
        return FillReport(mode="draft", status="error", error=PAGE_ERROR)
    if not filler.photos():
        return FillReport(mode="draft", status="error", error=PHOTOS_ERROR)

    listing = article.listing
    filler.step("Titre", lambda: filler.text("title", "Titre", listing.title))
    filler.step(
        "Description", lambda: filler.text("description", "Description", listing.description)
    )
    filler.step("Catégorie", filler.category)
    filler.step("Marque", filler.brand)
    filler.step("Taille", filler.size)
    filler.step("État", filler.condition)
    filler.step("Couleur", filler.colors)
    filler.step("Prix", filler.price)
    filler.step("Taille du colis", filler.parcel)

    # Une annonce incomplète est toujours enregistrée en brouillon.
    actual: Mode = "publish" if mode == "publish" and not filler.missing else "draft"
    url = filler.save(actual)
    if url is None:
        return FillReport(
            mode=actual, status="error", missing_fields=filler.missing, error=SAVE_ERROR
        )
    return FillReport(
        mode=actual,
        status="partial" if filler.missing else "ok",
        missing_fields=filler.missing,
        url=url,
    )
