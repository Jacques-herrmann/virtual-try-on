"""Scénario de la vidéo : chaque étape porte son sous-titre, minuté pendant le tournage."""

import base64
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from vto.tools.tutorial.captions import Cue

MIN_CUE = 2.5  # secondes : durée minimale d'un sous-titre
READING_SPEED = 15  # caractères lus par seconde
GAP = 0.15  # blanc entre deux sous-titres


def reading_time(text: str) -> float:
    return max(MIN_CUE, len(text) / READING_SPEED + 0.5)


@dataclass
class Demo:
    photo: Path
    garment_type: str  # valeur (« robe ») ; le front affiche « Robe »
    audience: str
    price: str  # prix retouché à la relecture
    draft_image: Path | None = None  # capture d'un brouillon Vinted, plan final


def label(value: str) -> str:
    return value[:1].upper() + value[1:]


@dataclass
class Director:
    page: object
    t0: float  # instant du début de l'enregistrement vidéo
    cues: list[Cue] = field(default_factory=list)
    pos: tuple[float, float] = (640.0, 400.0)

    def now(self) -> float:
        return time.monotonic() - self.t0

    @contextmanager
    def say(self, text: str, min_seconds: float | None = None) -> Iterator[None]:
        start = self.now()
        yield
        remaining = (min_seconds or reading_time(text)) - (self.now() - start)
        if remaining > 0:
            self.wait(remaining)
        self.cues.append(Cue(start, self.now() - GAP, text))

    def wait(self, seconds: float) -> None:
        self.page.wait_for_timeout(seconds * 1000)

    def move_to(self, locator, duration: float = 0.6) -> tuple[float, float]:
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box()
        if box is None:
            raise RuntimeError(f"élément invisible : {locator}")
        target = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        steps = max(int(duration * 50), 1)
        (x0, y0), (x1, y1) = self.pos, target
        for i in range(1, steps + 1):
            t = i / steps
            ease = t * t * (3 - 2 * t)
            self.page.mouse.move(x0 + (x1 - x0) * ease, y0 + (y1 - y0) * ease)
            self.page.wait_for_timeout(16)
        self.pos = target
        return target

    def click(self, locator) -> None:
        self.move_to(locator)
        self.wait(0.15)
        self.page.mouse.click(*self.pos)
        self.wait(0.3)

    def type(self, locator, text: str) -> None:
        self.click(locator)
        self.page.keyboard.press("Control+A")
        self.page.keyboard.type(text, delay=90)


def intro(d: Director) -> None:
    page = d.page
    page.get_by_text("Ajoute ton premier vêtement").wait_for()
    with d.say("Bienvenue ! Une photo de ton vêtement suffit pour créer ton annonce Vinted."):
        d.wait(1.0)
    with d.say("Clique sur « Nouvel article »."):
        d.click(page.locator('[data-tour="new-article"]'))


def full(d: Director, demo: Demo) -> None:
    page = d.page
    intro(d)
    dialog = page.locator(".p-dialog")

    with d.say("Ajoute une ou plusieurs photos de ton vêtement."):
        d.move_to(dialog.locator('[data-tour="photos"]'))
        dialog.locator("input[type=file]").set_input_files(str(demo.photo))
        d.wait(0.8)
    with d.say("Choisis le type de vêtement et pour qui il est."):
        d.click(dialog.locator("#type"))
        d.click(page.locator(".p-select-option", has_text=label(demo.garment_type)).first)
        d.click(dialog.locator(".p-selectbutton button", has_text=label(demo.audience)))
    with d.say("Le reste est facultatif : l’IA propose marque, taille, état et prix."):
        d.move_to(dialog.locator('[data-tour="optional-fields"]'))
        d.wait(0.6)
    with d.say("Clique sur « Générer »."):
        d.click(dialog.locator('[data-tour="generate"]'))

    card = page.locator('[data-tour="article-card"]').first
    with d.say("Kaloé crée les photos portées et rédige l’annonce, pendant que tu continues."):
        card.get_by_text("À relire").wait_for(timeout=180_000)
    with d.say("C’est prêt : ouvre l’article pour le relire."):
        d.click(card.locator(".open"))

    with d.say("Vérifie les photos : « Régénérer » en refait une, « Écarter » la retire."):
        page.locator('[data-tour="scene-photos"] img').last.wait_for()
        d.move_to(page.locator('[data-tour="scene-photos"] .tile').nth(1))
        d.wait(0.6)
        d.move_to(page.locator('[data-tour="scene-photos"] .tile').last)
    with d.say("Relis l’annonce et corrige ce que tu veux, ici le prix."):
        d.move_to(page.locator("#title"))
        d.type(page.locator("#lprice"), demo.price)
        page.keyboard.press("Tab")
    with d.say("Tout est bon ? Valide l’article. Rien ne part sans ta validation."):
        d.click(page.locator('[data-tour="validate"]'))
        page.get_by_text("Article validé : il est prêt").wait_for()

    with d.say("Dans tes articles, coche ceux à envoyer…"):
        d.click(page.locator(".back"))
        d.click(page.locator('[data-tour="article-card"] .pick').first)
    with d.say("… puis clique sur « Envoyer sur Vinted »."):
        d.click(page.locator('[data-test="selection-bar"] button', has_text="Envoyer sur Vinted"))
    with d.say("Kaloé remplit le formulaire Vinted à ta place, article par article."):
        card.get_by_text("Brouillon Vinted").wait_for(timeout=60_000)

    if demo.draft_image is not None:
        data = base64.b64encode(demo.draft_image.read_bytes()).decode()
        with d.say("Et voilà : ton annonce t’attend en brouillon sur Vinted.", min_seconds=4.0):
            page.set_content(
                "<body style='margin:0;background:#fbf7f2;display:grid;place-items:center;"
                f"height:100vh'><img src='data:image/png;base64,{data}' "
                "style='max-width:100%;max-height:100vh'></body>"
            )


def short(d: Director, demo: Demo) -> None:
    """Version courte pour le test automatique : les deux premières étapes."""
    intro(d)
