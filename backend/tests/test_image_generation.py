import random
from collections import deque

import pytest
from PIL import Image

from fakes import FakeClient
from vto.core import paths, scenes
from vto.core.config import Settings
from vto.core.errors import NoBackground
from vto.core.generation.image import generate_scene_image


def test_generates_and_saves_scene_image(data_dir, make_scene, make_article):
    make_scene("mannequin", prompt="Habille la {garment_type}.")
    scene = scenes.list_scenes()[0]
    article = make_article("robe")
    client = FakeClient()

    rel = generate_scene_image(client, Settings(image_model="img-m"), scene, article)

    assert rel == "generated/mannequin.jpg"
    out = paths.article_dir(article.id) / rel
    assert Image.open(out).format == "JPEG"
    call = client.calls[0]
    assert (call.kind, call.model, call.prompt, call.n_images) == (
        "image", "img-m", "Habille la robe.", 2,
    )


def test_sends_background_then_garment(data_dir, make_scene, make_article, monkeypatch):
    make_scene("m")
    scene = scenes.list_scenes()[0]
    article = make_article("robe")
    sent = []

    class Spy(FakeClient):
        def generate_image(self, model, prompt, images):
            sent.extend(img.getpixel((0, 0)) for img in images)
            return super().generate_image(model, prompt, images)

    generate_scene_image(Spy(), Settings(), scene, article, rng=random.Random(0))
    def is_blue(px):
        return px[2] > 200 and px[0] < 50

    assert is_blue(sent[1])  # 2e image = photo du vêtement (bleue)
    assert not is_blue(sent[0])


def test_no_background_propagates(data_dir, make_scene, make_article):
    make_scene("m", bgs=("robe/r.jpg",))
    scene = scenes.list_scenes()[0]
    with pytest.raises(NoBackground):
        generate_scene_image(FakeClient(image_responses=deque()), Settings(), scene,
                             make_article("haut"))
