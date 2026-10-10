import hashlib

import pytest

from vto.core import config, paths, scenes, storage
from vto.tools import import_legacy as il


@pytest.fixture
def batch(tmp_path, make_image):
    b = tmp_path / "batch"
    bg = b / "input" / "backgrounds"
    make_image(bg / "f" / "1" / "base.png", size=(3000, 4000))
    make_image(bg / "f" / "2" / "v1.jpg")
    make_image(bg / "h" / "1" / "base.png")
    make_image(bg / "c" / "1" / "base.png")
    clothes = b / "input" / "clothes"
    make_image(clothes / "f_pull_vert_blanc" / "photo.jpg")
    make_image(clothes / "f_pull_vert_blanc" / "base.png")
    (clothes / "f_pull_vert_blanc" / "infos.txt").write_text("Zara, taille M", encoding="utf-8")
    make_image(clothes / "c_baskets_blanches" / "x.jpg")
    make_image(clothes / "h_truc" / "x.jpg")
    (clothes / "vide").mkdir()
    return b


@pytest.fixture
def defaults(tmp_path, monkeypatch):
    src = tmp_path / "defaults"
    for slug in ("mannequin", "cintre"):
        (src / slug).mkdir(parents=True)
        (src / slug / "prompt.md").write_text(f"prompt {slug}", encoding="utf-8")
        (src / slug / "meta.json").write_text(f'{{"name": "{slug}"}}', encoding="utf-8")
    monkeypatch.setattr(scenes, "DEFAULT_SCENES_SOURCE", src)
    return src


def tree_hash(root):
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        h.update(str(p.relative_to(root)).encode())
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


@pytest.mark.parametrize(
    ("name", "garment_type", "audience"),
    [
        ("f_pull_vert_blanc", "haut", "femme"),
        ("h_jean_brut", "pantalon", "homme"),
        ("f_robe-longue", "robe", "femme"),
        ("c_baskets_blanches", "chaussures", None),
        ("h_truc", "autre", "homme"),
    ],
)
def test_guess_input(name, garment_type, audience):
    ui = il.guess_input(name, None)
    assert (ui.garment_type, ui.audience) == (garment_type, audience)


def test_import_into_user_data(data_dir, batch, defaults):
    before = tree_hash(batch)
    n, articles = il.import_into_user_data(batch)

    assert tree_hash(batch) == before  # source intacte
    assert n == 4
    mannequin = paths.scenes_dir() / "mannequin" / "backgrounds"
    assert (mannequin / "femme" / "base.jpg").is_file()
    assert (mannequin / "homme" / "base.jpg").is_file()
    assert (mannequin / "chaussures" / "base.jpg").is_file()
    assert (paths.scenes_dir() / "cintre" / "backgrounds" / "femme" / "v1.jpg").is_file()
    assert [s.slug for s in scenes.list_scenes()] == ["cintre", "mannequin"]

    by_type = {a.input.garment_type: a for a in articles}
    assert len(articles) == 3  # le dossier vide est ignoré
    pull = by_type["haut"]
    assert pull.input.audience == "femme"
    assert pull.input.notes == "Zara, taille M"
    assert pull.photos[0] == "photos/001.png"  # base.* en premier
    assert storage.load(pull.id) == pull

    assert config.load_settings().signature == il.LEGACY_SIGNATURE


def test_backgrounds_are_downscaled(data_dir, batch, defaults):
    il.import_into_user_data(batch)
    from PIL import Image

    img = Image.open(paths.scenes_dir() / "mannequin" / "backgrounds" / "femme" / "base.jpg")
    assert max(img.size) == 1536


def test_existing_signature_is_kept(data_dir, batch, defaults):
    config.save_settings(config.Settings(signature="à moi"))
    il.import_into_user_data(batch)
    assert config.load_settings().signature == "à moi"


def test_as_default_pack_writes_only_backgrounds(data_dir, batch, tmp_path):
    target = tmp_path / "pack"
    il.main([str(batch), "--as-default-pack", str(target)])
    assert (target / "mannequin" / "backgrounds" / "femme" / "base.jpg").is_file()
    assert not list(paths.articles_dir().iterdir())
