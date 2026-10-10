import json

import pytest

from vto.core import paths, scenes
from vto.core.errors import VtoError


def infos():
    return {i.slug: i for i in scenes.list_scene_infos()}


def test_list_scene_infos_reports_problems(data_dir, make_scene):
    make_scene("ok", order=2)
    make_scene("off", order=1, enabled=False)
    make_scene("nobg", order=3, bgs=())
    make_scene("noprompt", order=4, prompt=None)
    broken = make_scene("broken", order=5)
    (broken / "meta.json").write_text("{pas du json", encoding="utf-8")

    result = scenes.list_scene_infos()
    by_slug = {i.slug: i for i in result}
    assert [i.slug for i in result][:3] == ["off", "ok", "nobg"]
    assert by_slug["ok"].problem is None
    assert by_slug["off"].problem is None and by_slug["off"].enabled is False
    assert by_slug["nobg"].problem == "aucun décor"
    assert by_slug["noprompt"].problem == "prompt.md manquant"
    assert by_slug["broken"].problem == "meta.json invalide"
    assert by_slug["broken"].name == "broken"


def test_create_scene(data_dir, make_scene):
    make_scene("existante", order=4)
    info = scenes.create_scene("  Robe d'été  ")
    assert info.slug == "robe-d-ete"
    assert info.name == "Robe d'été"
    folder = paths.scenes_dir() / "robe-d-ete"
    assert "{garment_type}" in (folder / "prompt.md").read_text(encoding="utf-8")
    assert (folder / "backgrounds").is_dir()
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    assert meta == {"name": "Robe d'été", "enabled": True, "order": 5}
    assert infos()["robe-d-ete"].problem == "aucun décor"


def test_create_scene_unique_slug(data_dir):
    scenes.create_scene("Plage")
    assert scenes.create_scene("plage").slug == "plage-2"
    assert scenes.create_scene("PLAGE").slug == "plage-3"


def test_create_scene_without_ascii_letters(data_dir):
    assert scenes.create_scene("???").slug == "scene"


def test_create_scene_requires_name(data_dir):
    with pytest.raises(VtoError):
        scenes.create_scene("   ")


def test_update_scene_fields(data_dir, make_scene):
    make_scene("cintre", order=2)
    scenes.update_scene("cintre", name="Cintre bois")
    scenes.update_scene("cintre", enabled=False)
    scenes.update_scene("cintre", order=7)
    scenes.update_scene("cintre", prompt="Nouveau {garment_type}")
    info = infos()["cintre"]
    assert (info.name, info.enabled, info.order) == ("Cintre bois", False, 7)
    assert scenes.get_prompt("cintre") == "Nouveau {garment_type}"


def test_update_scene_repairs_invalid_meta(data_dir, make_scene):
    folder = make_scene("cintre")
    (folder / "meta.json").write_text("{", encoding="utf-8")
    scenes.update_scene("cintre", enabled=False)
    info = infos()["cintre"]
    assert info.problem is None and info.enabled is False and info.name == "cintre"


def test_update_scene_rejects_empty_name(data_dir, make_scene):
    make_scene("cintre")
    with pytest.raises(VtoError):
        scenes.update_scene("cintre", name=" ")


def test_delete_scene(data_dir, make_scene):
    make_scene("cintre")
    scenes.delete_scene("cintre")
    assert not (paths.scenes_dir() / "cintre").exists()


@pytest.mark.parametrize("slug", ["inconnue", "..", ".", "../scenes", "a/b", ""])
def test_unknown_or_unsafe_slug(data_dir, make_scene, slug):
    make_scene("cintre")
    with pytest.raises(VtoError):
        scenes.delete_scene(slug)
    assert (paths.scenes_dir() / "cintre").is_dir()
    assert paths.scenes_dir().is_dir()


def test_list_backgrounds(data_dir, make_scene, make_image):
    folder = make_scene("cintre", bgs=("fond.jpg",))
    make_image(folder / "backgrounds" / "robe" / "01.png")
    (folder / "backgrounds" / "notes.txt").write_text("x", encoding="utf-8")
    assert scenes.list_backgrounds("cintre") == ["fond.jpg", "robe/01.png"]


@pytest.mark.parametrize("subfolder", [None, "robe", "femme"])
def test_add_background(data_dir, make_scene, make_image, tmp_path, subfolder):
    make_scene("cintre", bgs=())
    src = make_image(tmp_path / "upload" / "tmp123.jpg")
    rel = scenes.add_background("cintre", src, subfolder, filename="Salon.JPG")
    expected = f"{subfolder}/Salon.JPG" if subfolder else "Salon.JPG"
    assert rel == expected
    assert rel in scenes.list_backgrounds("cintre")
    assert src.exists()


def test_add_background_name_collision(data_dir, make_scene, make_image, tmp_path):
    make_scene("cintre", bgs=("a.jpg",))
    src = make_image(tmp_path / "a.jpg")
    assert scenes.add_background("cintre", src, None) == "a-2.jpg"
    assert scenes.add_background("cintre", src, None) == "a-3.jpg"


def test_add_background_rejects_unknown_subfolder(data_dir, make_scene, make_image, tmp_path):
    make_scene("cintre")
    with pytest.raises(VtoError):
        scenes.add_background("cintre", make_image(tmp_path / "a.jpg"), "../..")
    with pytest.raises(VtoError):
        scenes.add_background("cintre", make_image(tmp_path / "b.jpg"), "plage")


def test_add_background_rejects_non_image(data_dir, make_scene, tmp_path):
    make_scene("cintre")
    src = tmp_path / "virus.exe"
    src.write_bytes(b"MZ")
    with pytest.raises(VtoError):
        scenes.add_background("cintre", src, None)


def test_add_background_strips_directories_from_filename(
    data_dir, make_scene, make_image, tmp_path
):
    make_scene("cintre", bgs=())
    rel = scenes.add_background("cintre", make_image(tmp_path / "a.jpg"), None, "../../x.jpg")
    assert rel == "x.jpg"


def test_delete_background(data_dir, make_scene):
    make_scene("cintre", bgs=("a.jpg", "b.jpg"))
    scenes.delete_background("cintre", "a.jpg")
    assert scenes.list_backgrounds("cintre") == ["b.jpg"]


@pytest.mark.parametrize("rel", ["../prompt.md", "../../cintre/meta.json", "inconnu.jpg", ""])
def test_delete_background_refuses_outside_or_missing(data_dir, make_scene, rel):
    folder = make_scene("cintre", bgs=("a.jpg",))
    with pytest.raises(VtoError):
        scenes.delete_background("cintre", rel)
    assert (folder / "prompt.md").is_file() and (folder / "meta.json").is_file()


def test_delete_background_refuses_absolute_path(data_dir, make_scene, tmp_path):
    victim = tmp_path / "victim.jpg"
    victim.write_bytes(b"x")
    make_scene("cintre")
    with pytest.raises(VtoError):
        scenes.delete_background("cintre", str(victim))
    assert victim.exists()
