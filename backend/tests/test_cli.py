import json
from collections import deque

import pytest
from PIL import Image
from typer.testing import CliRunner

from fakes import FakeClient
from vto import cli
from vto.core import config, errors, storage
from vto.core.models import ArticleStatus, Listing

runner = CliRunner()
LISTING = Listing(title="Zara robe M bleu", description="Jolie robe.")


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeClient(json_responses=deque([LISTING] * 5))
    monkeypatch.setattr(cli, "get_client", lambda settings: client)
    return client


@pytest.fixture
def photo(tmp_path, make_image):
    return make_image(tmp_path / "in" / "robe.png")


def invoke(*args):
    result = runner.invoke(cli.app, [str(a) for a in args])
    return result


def test_set_key(data_dir):
    assert invoke("config", "set-key", "abc").exit_code == 0
    assert config.load_settings().gemini_api_key == "abc"


def test_add_creates_article(data_dir, photo):
    result = invoke("add", photo, "--type", "robe", "--brand", "Zara", "--price", "12")
    assert result.exit_code == 0, result.output
    article = storage.load(result.output.strip())
    assert (article.input.brand, article.input.price) == ("Zara", 12.0)


def test_add_rejects_unknown_type(data_dir, photo):
    result = invoke("add", photo, "--type", "chapeau")
    assert result.exit_code == 1
    assert "Saisie invalide" in result.output


def test_run_list_show_and_regen(data_dir, make_scene, photo, fake_client):
    make_scene("mannequin")
    article_id = invoke("add", photo, "--type", "robe").output.strip()

    result = invoke("run")
    assert result.exit_code == 0, result.output
    assert storage.load(article_id).status == ArticleStatus.TO_REVIEW

    assert "Zara robe M bleu" in invoke("list").output
    assert "mannequin" in invoke("show", article_id).output

    fake_client.calls.clear()
    assert invoke("regen", article_id, "--scene", "mannequin").exit_code == 0
    assert [c.kind for c in fake_client.calls] == ["image"]


def test_run_without_drafts(data_dir):
    assert "Aucun article" in invoke("run").output


def test_vto_error_is_shown_without_traceback(data_dir, make_scene, photo, monkeypatch):
    make_scene("mannequin")
    invoke("add", photo, "--type", "robe")
    monkeypatch.setattr(cli, "get_client", lambda s: (_ for _ in ()).throw(errors.MissingApiKey()))
    result = invoke("run")
    assert result.exit_code == 1
    assert errors.MissingApiKey.user_message in result.output
    assert "Traceback" not in result.output


def test_export_for_legacy_script(data_dir, make_scene, photo, fake_client, tmp_path):
    make_scene("mannequin", order=1)
    make_scene("cintre", order=2)
    article_id = invoke("add", photo, "--type", "robe").output.strip()
    invoke("run")
    out = tmp_path / "export"
    assert invoke("export", article_id, out).exit_code == 0
    assert sorted(p.name for p in out.glob("*.jpg")) == ["00.jpg", "01.jpg", "02.jpg"]
    assert Image.open(out / "02.jpg").format == "JPEG"  # photo d'origine PNG convertie
    data = json.loads((out / "description.json").read_text(encoding="utf-8"))
    expected_keys = {"title", "description", "category", "brand", "size", "condition",
                     "color", "price", "parcel_size"}
    assert expected_keys <= data.keys()
    assert isinstance(data["color"], list)


def test_export_requires_listing(data_dir, photo, tmp_path):
    article_id = invoke("add", photo, "--type", "robe").output.strip()
    result = invoke("export", article_id, tmp_path / "x")
    assert result.exit_code == 1
