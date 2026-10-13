import os

from vto.core import config, errors, paths


def test_get_settings_never_returns_key(api):
    config.save_settings(config.Settings(gemini_api_key="AIzaSECRET1234"))
    r = api.get("/api/settings")
    body = r.json()
    assert body["has_key"] is True and body["key_hint"] == "1234"
    assert "SECRET" not in r.text
    assert body["listing_prompt"] == config.default_listing_prompt()
    assert {"signature", "image_model", "text_model"} <= body.keys()


def test_get_settings_without_key(make_api, fake):
    api = make_api(lambda k: fake, api_key=None)
    body = api.get("/api/settings").json()
    assert body["has_key"] is False and body["key_hint"] is None


def test_put_settings(api):
    r = api.put(
        "/api/settings",
        json={"signature": "Merci !", "image_model": "img-2", "gemini_api_key": "pirate"},
    )
    assert r.status_code == 200
    saved = config.load_settings()
    assert saved.signature == "Merci !" and saved.image_model == "img-2"
    assert saved.gemini_api_key == "k"  # la clé ne passe que par check-key
    assert saved.text_model == config.DEFAULT_TEXT_MODEL


def test_put_settings_rejects_empty_model(api):
    r = api.put("/api/settings", json={"text_model": "  "})
    assert r.status_code == 400


def test_reset_listing_prompt(api):
    api.put("/api/settings", json={"listing_prompt": "perso"})
    r = api.post("/api/settings/reset-listing-prompt")
    assert r.json()["listing_prompt"] == config.default_listing_prompt()


def test_check_key_valid_saves_and_resumes(make_api, fake):
    api = make_api(lambda k: fake, api_key=None)
    queue = api.app.state.queue
    queue._paused, queue._reason = True, "x"
    r = api.post("/api/settings/check-key", json={"key": "  nouvelle-cle-5678 "})
    assert r.status_code == 200
    assert r.json()["has_key"] is True and r.json()["key_hint"] == "5678"
    assert config.load_settings().gemini_api_key == "nouvelle-cle-5678"
    assert fake.checked == [[config.DEFAULT_IMAGE_MODEL, config.DEFAULT_TEXT_MODEL]]
    assert queue.status()["paused"] is False


def test_check_key_invalid_keeps_previous(api, fake):
    fake.check_error = errors.InvalidApiKey()
    r = api.post("/api/settings/check-key", json={"key": "mauvaise"})
    assert r.status_code == 400
    assert r.json()["message"] == errors.InvalidApiKey.user_message
    assert config.load_settings().gemini_api_key == "k"


def test_open_logs(api, monkeypatch):
    opened = []
    monkeypatch.setattr(os, "startfile", opened.append, raising=False)
    assert api.post("/api/system/open-logs").status_code == 204
    assert opened == [paths.logs_dir()]


def test_queue_routes(api):
    assert api.get("/api/queue").json() == {
        "running": None, "pending": [], "paused": False, "reason": None,
    }
    api.app.state.queue._paused = True
    assert api.post("/api/queue/resume").json()["paused"] is False


def test_get_settings_exposes_tutorial(api):
    body = api.get("/api/settings").json()
    assert body["tutorial"] == {"video_seen": False, "tours_seen": []}


def test_put_tutorial_replaces_it(api):
    tutorial = {"video_seen": True, "tours_seen": ["articles"]}
    r = api.put("/api/settings", json={"tutorial": tutorial})
    assert r.json()["tutorial"] == tutorial
    assert config.load_settings().tutorial.tours_seen == ["articles"]

    api.put("/api/settings", json={"signature": "Merci !"})
    assert config.load_settings().tutorial.video_seen is True  # intact sans `tutorial`

    r = api.put("/api/settings", json={"tutorial": {"video_seen": True, "tours_seen": []}})
    assert r.json()["tutorial"]["tours_seen"] == []
