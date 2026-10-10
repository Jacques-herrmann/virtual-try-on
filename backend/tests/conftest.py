from pathlib import Path

import pytest
from PIL import Image


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
