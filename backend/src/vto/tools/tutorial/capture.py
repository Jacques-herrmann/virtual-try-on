"""Données de tournage : passage Gemini réel sur la démo, ou article déjà généré dans l'app."""

import json
import os
import shutil
import tempfile
from pathlib import Path

from vto.core import config, paths, pipeline, scenes, storage
from vto.core.models import Article, UserInput
from vto.tools.tutorial.replay import IMAGES, LISTING, RecordingClient, save_image, save_listing
from vto.vinted import remote
from vto.vinted.catalog import Catalog
from vto.vinted.schema import VintedData

PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
ARTICLE_PHOTO = "article-"  # photos recopiées par capture_from_article


class CaptureError(Exception):
    pass


def demo_photos(demo: Path) -> list[Path]:
    photos = sorted(p for p in demo.iterdir() if p.suffix.lower() in PHOTO_SUFFIXES)
    if not photos:
        raise CaptureError(f"Aucune photo de vêtement dans {demo}.")
    return photos


def demo_input(demo: Path) -> UserInput:
    return UserInput.model_validate_json((demo / "input.json").read_text(encoding="utf-8"))


def _clear_capture(out: Path) -> None:
    """Seules nos sorties précédentes sont remplacées."""
    shutil.rmtree(out / IMAGES, ignore_errors=True)
    (out / LISTING).unlink(missing_ok=True)


def _summary(article: Article, out: Path) -> str:
    lines = [
        f"{s.scene} : {s.status}" + (f" ({s.error})" if s.error else "") for s in article.scenes
    ]
    if article.listing is not None:
        lines.append(json.dumps(article.listing.model_dump(mode="json"), ensure_ascii=False))
    lines.append(f"Images : {out / IMAGES}")
    return "\n".join(lines)


def find_article(query: str) -> Article:
    """Article du dossier de données de l'app, par identifiant ou par un mot de son titre."""
    needle = query.casefold()
    found = [
        a for a in storage.list_articles()
        if a.id.casefold() == needle or needle in (a.listing.title if a.listing else "").casefold()
    ]
    if not found:
        raise CaptureError(f"Aucun article ne correspond à « {query} » dans {paths.data_dir()}.")
    if len(found) > 1:
        names = ", ".join(f"{a.id} ({a.listing.title})" for a in found if a.listing)
        raise CaptureError(f"Plusieurs articles correspondent : {names}. Préciser l'identifiant.")
    return found[0]


def capture_from_article(query: str, demo: Path, out: Path) -> str:
    """Reprend un article déjà généré dans l'app (celui envoyé en brouillon sur Vinted).

    Lecture seule sur les données de l'app. Les images sont rangées sous les prompts du pack
    par défaut, ceux que le tournage utilise.
    """
    article = find_article(query)
    if article.listing is None or not article.photos:
        raise CaptureError(f"L'article {article.id} n'a pas encore d'annonce.")
    others = [
        p.name for p in (demo.iterdir() if demo.is_dir() else [])
        if p.suffix.lower() in PHOTO_SUFFIXES and not p.name.startswith(ARTICLE_PHOTO)
    ]
    if others:
        raise CaptureError(f"{demo} contient déjà des photos ({', '.join(others)}) : les déplacer.")

    folder = paths.article_dir(article.id)
    defaults = scenes.default_scenes_source()
    _clear_capture(out)
    for result in article.scenes:
        prompt_file = defaults / result.scene / "prompt.md"
        if result.status != "ok" or not result.image or not prompt_file.is_file():
            continue  # scène en échec, ou scène du vendeur absente du film
        prompt = prompt_file.read_text(encoding="utf-8")
        prompt = prompt.replace("{garment_type}", article.input.garment_type)
        save_image(out, prompt, (folder / result.image).read_bytes())
    save_listing(out, article.listing.model_dump(mode="json"))

    demo.mkdir(parents=True, exist_ok=True)
    for old in demo.glob(f"{ARTICLE_PHOTO}*"):
        old.unlink()
    photo = folder / article.photos[0]
    shutil.copyfile(photo, demo / f"{ARTICLE_PHOTO}01{photo.suffix.lower()}")
    demo_choice = {"garment_type": article.input.garment_type, "audience": article.input.audience}
    (demo / "input.json").write_text(json.dumps(demo_choice, indent=2) + "\n", encoding="utf-8")
    return _summary(article, out)


def capture(demo: Path, out: Path) -> str:
    """Génère les images et l'annonce avec le vrai Gemini ; rend un résumé lisible."""
    if not os.environ.get("GEMINI_API_KEY"):
        raise CaptureError("GEMINI_API_KEY manquante (fichier .env ou variable d'environnement).")
    user_input, photos = demo_input(demo), demo_photos(demo)
    _clear_capture(out)

    with tempfile.TemporaryDirectory(prefix="kaloe-capture-", ignore_cleanup_errors=True) as tmp:
        saved = os.environ.get("VTO_DATA_DIR")
        os.environ["VTO_DATA_DIR"] = tmp
        try:
            scenes.ensure_default_scenes()
            settings = config.load_settings()
            client = RecordingClient(inner=pipeline.build_client(settings), folder=out)
            catalog = Catalog(VintedData.model_validate_json(remote.bundled_text()))
            article = storage.create_article(user_input, photos)
            article = pipeline.process_article(
                article.id, client=client, settings=settings, choices_for=catalog.choices_for
            )
        finally:
            if saved is None:
                os.environ.pop("VTO_DATA_DIR", None)
            else:
                os.environ["VTO_DATA_DIR"] = saved
    return _summary(article, out)
