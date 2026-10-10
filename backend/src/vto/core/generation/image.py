"""Génération de l'image d'une scène pour un article."""

import io
import random

from PIL import Image

from vto.core import paths, scenes
from vto.core.config import Settings
from vto.core.generation.client import GenAIClient
from vto.core.images import load_image, resize_max, save_jpeg
from vto.core.models import Article


def generate_scene_image(
    client: GenAIClient,
    settings: Settings,
    scene: scenes.Scene,
    article: Article,
    rng: random.Random | None = None,
) -> str:
    """Génère l'image et renvoie son chemin relatif au dossier de l'article."""
    garment_type = article.input.garment_type
    keys = (garment_type, article.input.audience)
    background = resize_max(load_image(scenes.pick_background(scene, keys, rng)))
    article_dir = paths.article_dir(article.id)
    garment = resize_max(load_image(article_dir / article.photos[0]))

    # Ordre attendu par les prompts : [Image A] = décor, [Image B] = vêtement.
    data = client.generate_image(
        settings.image_model,
        scenes.render_prompt(scene, garment_type),
        [background, garment],
    )

    relative = f"generated/{scene.slug}.jpg"
    with Image.open(io.BytesIO(data)) as generated:
        save_jpeg(generated, article_dir / relative)
    return relative
