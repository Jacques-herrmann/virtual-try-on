import json
from pathlib import Path

import pytest
from PIL import Image

from vto.core import paths


@pytest.fixture
def data_dir(tmp_path, monkeypatch) -> Path:
    """Isole les données utilisateur dans un dossier temporaire."""
    root = tmp_path / "data"
    monkeypatch.setenv("VTO_DATA_DIR", str(root))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return root


@pytest.fixture
def make_image():
    """Écrit une image unie à `path` et renvoie le chemin."""

    def _make(path: Path, size=(64, 48), color=(200, 30, 30)) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, color).save(path)
        return path

    return _make


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


@pytest.fixture
def make_article(tmp_path, make_image):
    from vto.core import storage
    from vto.core.models import UserInput

    def _make(garment_type="robe", **fields):
        photo = make_image(tmp_path / "src" / f"{garment_type}.jpg", color=(0, 0, 255))
        return storage.create_article(UserInput(garment_type=garment_type, **fields), [photo])

    return _make
