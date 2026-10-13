import json

import pytest
from PIL import Image

from vto.core.models import Listing
from vto.tools.tutorial import captions, replay


def test_webvtt_from_step_times():
    cues = [
        captions.Cue(0.4, 3.25, "Ajoute une photo de ton vêtement."),
        captions.Cue(3.5, 65.0, "Kaloé crée les photos portées\net rédige l’annonce."),
    ]
    assert captions.to_webvtt(cues) == (
        "WEBVTT\n\n"
        "00:00:00.400 --> 00:00:03.250\nAjoute une photo de ton vêtement.\n\n"
        "00:00:03.500 --> 00:01:05.000\nKaloé crée les photos portées\net rédige l’annonce.\n"
    )


def test_webvtt_shifts_by_trimmed_start_and_drops_empty_cues():
    cues = [captions.Cue(1.0, 2.0, "Coupé"), captions.Cue(2.5, 6.0, "Gardé")]
    text = captions.to_webvtt(cues, offset=3.0)
    assert "Coupé" not in text
    assert "00:00:00.000 --> 00:00:03.000\nGardé" in text


def test_webvtt_rejects_overlaps():
    with pytest.raises(ValueError):
        captions.to_webvtt([captions.Cue(0, 3, "a"), captions.Cue(2, 4, "b")])


def test_replay_client_returns_captured_outputs(tmp_path):
    rec = replay.RecordingClient(inner=_Real(), folder=tmp_path)
    image = rec.generate_image("m", "scène 1", [Image.new("RGB", (4, 4))])
    listing = rec.generate_json("m", "annonce", [], Listing)
    assert json.loads((tmp_path / "listing.json").read_text(encoding="utf-8"))["title"] == "Robe"

    client = replay.ReplayClient(tmp_path, delay=0)
    assert client.generate_image("m", "scène 1", []) == image
    assert client.generate_json("m", "autre prompt", [], Listing) == listing
    client.check_models(["m"])


def test_replay_client_without_capture_explains(tmp_path):
    with pytest.raises(replay.MissingCapture, match="vto-tutorial capture"):
        replay.ReplayClient(tmp_path / "absent", delay=0)


def test_replay_client_unknown_prompt_fails(tmp_path):
    rec = replay.RecordingClient(inner=_Real(), folder=tmp_path)
    rec.generate_json("m", "annonce", [], Listing)
    rec.generate_image("m", "scène 1", [])
    with pytest.raises(replay.MissingCapture, match="scène"):
        replay.ReplayClient(tmp_path, delay=0).generate_image("m", "scène inconnue", [])


class _Real:
    def generate_image(self, model, prompt, images):
        return f"image:{prompt}".encode()

    def generate_json(self, model, prompt, images, schema):
        return schema(title="Robe", description="Jolie robe")

    def check_models(self, models):
        pass


def test_long_captions_stay_longer_on_screen():
    from vto.tools.tutorial.scenario import MIN_CUE, reading_time

    assert reading_time("Clique ici.") == MIN_CUE
    assert reading_time("x" * 75) == pytest.approx(5.5)


def test_all_tours_are_disabled_while_filming():
    import re
    from pathlib import Path

    from vto.tools.tutorial.harness import TOURS

    tours_ts = Path(__file__).parents[2] / "frontend/src/tours.ts"
    union = re.search(r"export type TourId =([^\n]+)", tours_ts.read_text(encoding="utf-8"))
    assert set(TOURS) == set(re.findall(r"'([^']+)'", union.group(1)))


def test_blur_filter_blurs_then_crops():
    from vto.tools.tutorial.video import Blur, Box, blur_filter

    graph = blur_filter([Blur.parse("10,20,300,40@4.5-9")], Box.parse("0,0,1200,700"))
    assert "crop=300:40:10:20,boxblur" in graph
    assert "overlay=10:20:enable='between(t,4.5,9.0)'" in graph
    assert graph.endswith("[v0]crop=1200:700:0:0,scale='min(1280,iw)':-2[out]")


@pytest.mark.browser
def test_record_short_video(tmp_path):
    import shutil

    from vto.api import app as api_app
    from vto.tools.tutorial import record

    if shutil.which("ffmpeg") is None or not (api_app.STATIC_DIR / "index.html").is_file():
        pytest.skip("ffmpeg ou front compilé absent")
    (tmp_path / "capture").mkdir()
    (tmp_path / "capture" / "listing.json").write_text('{"title": "Robe", "description": "d"}')
    mp4 = record(tmp_path, tmp_path / "out", short_version=True, price="15", delay=0)
    assert mp4.stat().st_size > 10_000
    vtt = (tmp_path / "out" / "kaloe.vtt").read_text(encoding="utf-8")
    assert vtt.startswith("WEBVTT") and "Nouvel article" in vtt
    assert (tmp_path / "out" / "kaloe.jpg").is_file()


def _generated_article(tmp_path):
    """Article déjà généré dans le dossier de données, comme après un passage dans l'app."""
    from vto.core import storage
    from vto.core.models import SceneResult, UserInput

    photo = tmp_path / "robe.jpg"
    Image.new("RGB", (8, 8), "red").save(photo)
    article = storage.create_article(UserInput(garment_type="robe", audience="femme"), [photo])
    folder = storage.paths.article_dir(article.id)
    for slug in ("mannequin", "cintre"):
        Image.new("RGB", (8, 8), "blue").save(folder / f"{slug}.png")
    article.scenes = [
        SceneResult(scene=s, status="ok", image=f"{s}.png") for s in ("mannequin", "cintre")
    ]
    article.listing = Listing(title="Robe longue fleurie", description="Jolie robe", price=15)
    storage.save(article)
    return article


def test_capture_from_article_replays_in_the_film(data_dir, tmp_path):
    from vto.core import scenes
    from vto.tools.tutorial.capture import capture_from_article

    article = _generated_article(tmp_path)
    base = tmp_path / "tutorial"
    summary = capture_from_article("fleurie", base / "demo", base / "capture")
    assert "Robe longue fleurie" in summary

    assert json.loads((base / "demo" / "input.json").read_text(encoding="utf-8")) == {
        "garment_type": "robe", "audience": "femme",
    }
    assert len(list((base / "demo").glob("article-*.jpg"))) == 1

    # Les prompts du film sont ceux du pack par défaut : chaque scène retrouve son image.
    client = replay.ReplayClient(base / "capture", delay=0)
    for slug in ("mannequin", "cintre"):
        prompt = (scenes.default_scenes_source() / slug / "prompt.md").read_text(encoding="utf-8")
        assert client.generate_image("m", prompt.replace("{garment_type}", "robe"), []).startswith(
            b"\x89PNG"
        )
    assert client.generate_json("m", "p", [], Listing).price == 15
    # Lecture seule : l'article d'origine est intact.
    from vto.core import storage

    assert storage.load(article.id) == article


def test_capture_from_article_refuses_ambiguous_or_foreign_photos(data_dir, tmp_path):
    from vto.tools.tutorial.capture import CaptureError, capture_from_article

    _generated_article(tmp_path)
    base = tmp_path / "tutorial"
    with pytest.raises(CaptureError, match="Aucun article"):
        capture_from_article("pantalon", base / "demo", base / "capture")

    (base / "demo").mkdir(parents=True)
    Image.new("RGB", (4, 4)).save(base / "demo" / "autre.jpg")
    with pytest.raises(CaptureError, match="autre.jpg"):
        capture_from_article("fleurie", base / "demo", base / "capture")
