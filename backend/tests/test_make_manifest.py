import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from vto.updates.manifest import Manifest

SCRIPT = Path(__file__).parents[2] / "packaging" / "make_manifest.py"


@pytest.fixture(scope="module")
def make_manifest():
    spec = importlib.util.spec_from_file_location("make_manifest", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def release(tmp_path):
    installer = tmp_path / "Kaloe-Setup-0.3.0.exe"
    installer.write_bytes(b"MZ installeur")
    minimum = tmp_path / "minimum_version.txt"
    minimum.write_text(" 0.2.0 \n", encoding="utf-8")
    notes = tmp_path / "notes.txt"
    notes.write_text("Bandeau de mise à jour.\n", encoding="utf-8")
    return installer, minimum, notes


def run(make_manifest, tmp_path, installer, minimum, notes, version="0.3.0"):
    out = tmp_path / "latest.json"
    args = [
        "--installer", str(installer),
        "--version", version,
        "--minimum-file", str(minimum),
        "--out", str(out),
    ]
    if notes is not None:
        args += ["--notes-file", str(notes)]
    make_manifest.main(args)
    return json.loads(out.read_text(encoding="utf-8"))


def test_manifest_is_valid(make_manifest, tmp_path, release):
    installer, minimum, notes = release
    data = run(make_manifest, tmp_path, installer, minimum, notes)
    manifest = Manifest(**data)
    assert manifest.version == "0.3.0"
    assert manifest.minimum_version == "0.2.0"
    assert manifest.sha256 == hashlib.sha256(b"MZ installeur").hexdigest()
    from vto.licensing.client import DEFAULT_URL

    assert manifest.url == f"{DEFAULT_URL}/updates/Kaloe-Setup-0.3.0.exe"
    assert manifest.notes == "Bandeau de mise à jour."


def test_base_url_can_be_overridden(make_manifest, tmp_path, release):
    installer, minimum, notes = release
    out = tmp_path / "latest.json"
    make_manifest.main([
        "--installer", str(installer),
        "--version", "0.3.0",
        "--minimum-file", str(minimum),
        "--base-url", "https://licence.example/",
        "--out", str(out),
    ])
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["url"] == "https://licence.example/updates/Kaloe-Setup-0.3.0.exe"


def test_notes_are_optional(make_manifest, tmp_path, release):
    installer, minimum, _ = release
    assert run(make_manifest, tmp_path, installer, minimum, None)["notes"] == ""


def test_minimum_after_version_is_refused(make_manifest, tmp_path, release):
    installer, minimum, notes = release
    minimum.write_text("0.4.0", encoding="utf-8")
    with pytest.raises(SystemExit):
        run(make_manifest, tmp_path, installer, minimum, notes)


def test_repo_minimum_file_is_valid(make_manifest):
    from packaging.version import Version

    Version(make_manifest.DEFAULT_MINIMUM_FILE.read_text(encoding="utf-8").strip())
