import io

import pytest
from PIL import Image

from vto.core import paths


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (30, 30), "blue").save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def scened(data_dir, make_scene):
    make_scene("mannequin", order=1)
    make_scene("vide", order=2, bgs=())


def test_list(api, scened):
    body = api.get("/api/scenes").json()
    assert [(s["slug"], s["problem"]) for s in body] == [
        ("mannequin", None),
        ("vide", "aucun décor"),
    ]
    assert {"name", "enabled", "order"} <= body[0].keys()


def test_create_and_detail(api, scened):
    r = api.post("/api/scenes", json={"name": "Plage"})
    assert r.status_code == 201 and r.json()["slug"] == "plage"
    detail = api.get("/api/scenes/plage").json()
    assert detail["name"] == "Plage"
    assert "{garment_type}" in detail["prompt"]
    assert detail["backgrounds"] == []


def test_create_requires_name(api, scened):
    assert api.post("/api/scenes", json={"name": " "}).status_code == 400


def test_update(api, scened):
    r = api.patch(
        "/api/scenes/mannequin",
        json={"name": "Mannequin doré", "enabled": False, "order": 9, "prompt": "P"},
    )
    assert r.status_code == 200
    detail = api.get("/api/scenes/mannequin").json()
    assert (detail["name"], detail["enabled"], detail["order"], detail["prompt"]) == (
        "Mannequin doré", False, 9, "P",
    )


def test_delete(api, scened):
    assert api.delete("/api/scenes/vide").status_code == 204
    assert not (paths.scenes_dir() / "vide").exists()
    assert api.get("/api/scenes/vide").status_code == 400


def test_backgrounds(api, scened):
    r = api.post(
        "/api/scenes/vide/backgrounds",
        data={"subfolder": "robe"},
        files=[
            ("files", ("salon.png", png(), "image/png")),
            ("files", ("b.png", png(), "image/png")),
        ],
    )
    assert r.status_code == 200
    assert r.json()["backgrounds"] == ["robe/b.png", "robe/salon.png"]
    assert r.json()["problem"] is None

    api.post("/api/scenes/vide/backgrounds", files=[("files", ("racine.png", png(), "image/png"))])
    assert api.get("/api/scenes/vide").json()["backgrounds"][0] == "racine.png"

    img = api.get("/files/scenes/vide/backgrounds/robe/salon.png")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"

    assert api.delete("/api/scenes/vide/backgrounds/robe/salon.png").status_code == 204
    assert "robe/salon.png" not in api.get("/api/scenes/vide").json()["backgrounds"]


def test_background_bad_subfolder(api, scened):
    r = api.post(
        "/api/scenes/vide/backgrounds",
        data={"subfolder": "plage"},
        files=[("files", ("a.png", png(), "image/png"))],
    )
    assert r.status_code == 400


def test_background_delete_refuses_escape(api, scened):
    assert api.delete("/api/scenes/mannequin/backgrounds/..%2Fprompt.md").status_code in (400, 404)
    assert (paths.scenes_dir() / "mannequin" / "prompt.md").is_file()


def test_scene_files_only_images(api, scened):
    assert api.get("/files/scenes/mannequin/prompt.md").status_code == 404
    assert api.get("/files/scenes/mannequin/meta.json").status_code == 404
