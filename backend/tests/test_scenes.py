import json
import random

import pytest

from vto.core import paths, scenes
from vto.core.errors import NoBackground


@pytest.fixture
def make_scene(make_image):
    def _make(slug, *, order=1, enabled=True, prompt="Habille {garment_type}.", bgs=("a.jpg",)):
        d = paths.scenes_dir() / slug
        d.mkdir(parents=True)
        (d / "meta.json").write_text(
            json.dumps({"name": slug.title(), "enabled": enabled, "order": order}),
            encoding="utf-8",
        )
        if prompt is not None:
            (d / "prompt.md").write_text(prompt, encoding="utf-8")
        for bg in bgs:
            make_image(d / "backgrounds" / bg)
        return d

    return _make


def test_list_scenes_sorted_and_filtered(data_dir, make_scene):
    make_scene("cintre", order=2)
    make_scene("mannequin", order=1)
    make_scene("off", order=3, enabled=False)
    assert [s.slug for s in scenes.list_scenes()] == ["mannequin", "cintre"]
    assert [s.slug for s in scenes.list_scenes(enabled_only=False)] == [
        "mannequin", "cintre", "off",
    ]


def test_list_scenes_skips_invalid(data_dir, make_scene, caplog):
    make_scene("noprompt", prompt=None)
    make_scene("nobg", bgs=())
    make_scene("ok")
    assert [s.slug for s in scenes.list_scenes()] == ["ok"]
    assert "noprompt" in caplog.text and "nobg" in caplog.text


def test_scene_fields(data_dir, make_scene):
    make_scene("mannequin", prompt="P")
    s = scenes.list_scenes()[0]
    assert (s.name, s.prompt, s.enabled, s.order) == ("Mannequin", "P", True, 1)


def test_pick_background_prefers_type_folder(data_dir, make_scene):
    make_scene("m", bgs=("generic.jpg", "chaussures/shoe.jpg"))
    s = scenes.list_scenes()[0]
    assert scenes.pick_background(s, "chaussures").name == "shoe.jpg"
    assert scenes.pick_background(s, "robe").name == "generic.jpg"


def test_pick_background_falls_back_when_type_folder_empty(data_dir, make_scene):
    d = make_scene("m", bgs=("generic.jpg",))
    (d / "backgrounds" / "robe").mkdir()
    assert scenes.pick_background(scenes.list_scenes()[0], "robe").name == "generic.jpg"


def test_pick_background_only_type_folders(data_dir, make_scene):
    make_scene("m", bgs=("robe/r.jpg",))
    s = scenes.list_scenes()[0]
    assert scenes.pick_background(s, "robe").name == "r.jpg"
    with pytest.raises(NoBackground):
        scenes.pick_background(s, "haut")


def test_pick_background_is_deterministic_with_seed(data_dir, make_scene):
    make_scene("m", bgs=tuple(f"{i}.jpg" for i in range(10)))
    s = scenes.list_scenes()[0]
    picks = {scenes.pick_background(s, "robe", random.Random(42)) for _ in range(3)}
    assert len(picks) == 1


def test_render_prompt_only_replaces_garment_type(data_dir, make_scene):
    make_scene("m", prompt="Une {garment_type} et {autre} {")
    s = scenes.list_scenes()[0]
    assert scenes.render_prompt(s, "robe") == "Une robe et {autre} {"


def test_ensure_default_scenes(data_dir, tmp_path, make_image):
    src = tmp_path / "defaults"
    (src / "mannequin").mkdir(parents=True)
    (src / "mannequin" / "prompt.md").write_text("x", encoding="utf-8")
    assert scenes.ensure_default_scenes(src) is True
    assert (paths.scenes_dir() / "mannequin" / "prompt.md").is_file()
    (paths.scenes_dir() / "mannequin" / "prompt.md").write_text("modifié", encoding="utf-8")
    assert scenes.ensure_default_scenes(src) is False
    assert (paths.scenes_dir() / "mannequin" / "prompt.md").read_text(encoding="utf-8") == "modifié"
