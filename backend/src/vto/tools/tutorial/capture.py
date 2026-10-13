"""Passage Gemini réel sur le vêtement de démo, enregistré pour le tournage (une fois)."""

import json
import os
import shutil
import tempfile
from pathlib import Path

from vto.core import config, pipeline, scenes, storage
from vto.core.models import UserInput
from vto.tools.tutorial.replay import IMAGES, LISTING, RecordingClient
from vto.vinted import remote
from vto.vinted.catalog import Catalog
from vto.vinted.schema import VintedData

PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class CaptureError(Exception):
    pass


def demo_photos(demo: Path) -> list[Path]:
    photos = sorted(p for p in demo.iterdir() if p.suffix.lower() in PHOTO_SUFFIXES)
    if not photos:
        raise CaptureError(f"Aucune photo de vêtement dans {demo}.")
    return photos


def demo_input(demo: Path) -> UserInput:
    return UserInput.model_validate_json((demo / "input.json").read_text(encoding="utf-8"))


def capture(demo: Path, out: Path) -> str:
    """Génère les images et l'annonce ; rend un résumé lisible."""
    if not os.environ.get("GEMINI_API_KEY"):
        raise CaptureError("GEMINI_API_KEY manquante (fichier .env ou variable d'environnement).")
    user_input, photos = demo_input(demo), demo_photos(demo)

    # Seules nos sorties précédentes sont remplacées.
    shutil.rmtree(out / IMAGES, ignore_errors=True)
    (out / LISTING).unlink(missing_ok=True)

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

    lines = [f"{s.scene} : {s.status}" + (f" ({s.error})" if s.error else "")
             for s in article.scenes]
    if article.listing is not None:
        lines.append(json.dumps(article.listing.model_dump(mode="json"), ensure_ascii=False))
    lines.append(f"Images : {out / IMAGES}")
    return "\n".join(lines)
