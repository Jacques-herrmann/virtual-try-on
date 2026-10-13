import json

from vto.core import config, paths


def test_defaults_when_no_file(data_dir):
    s = config.load_settings()
    assert s.api_key() is None
    assert s.image_model and s.text_model
    assert s.signature == ""
    assert "Idée de look" in s.listing_prompt


def test_save_then_load_round_trip(data_dir):
    s = config.load_settings()
    s.gemini_api_key = "k"
    s.signature = "Merci !"
    config.save_settings(s)
    assert config.load_settings() == s


def test_env_key_takes_precedence(data_dir, monkeypatch):
    s = config.Settings(gemini_api_key="from-file")
    monkeypatch.setenv("GEMINI_API_KEY", "from-env")
    assert s.api_key() == "from-env"


def test_env_key_is_not_persisted(data_dir, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "from-env")
    config.save_settings(config.load_settings())
    saved = json.loads(paths.settings_file().read_text(encoding="utf-8"))
    assert saved["gemini_api_key"] is None


def test_corrupted_file_falls_back_to_defaults(data_dir, caplog):
    paths.settings_file().write_text("{pas du json", encoding="utf-8")
    assert config.load_settings() == config.Settings()
    assert "settings.json" in caplog.text


def test_vinted_mode_defaults_to_draft(data_dir):
    assert config.load_settings().vinted_mode == "draft"


def test_old_settings_file_loads_without_loss(data_dir):
    old = {"gemini_api_key": "k", "signature": "Merci !", "listing_prompt": "P"}
    paths.settings_file().write_text(json.dumps(old), encoding="utf-8")
    s = config.load_settings()
    assert (s.gemini_api_key, s.signature, s.listing_prompt) == ("k", "Merci !", "P")
    assert s.vinted_mode == "draft"


def test_vinted_mode_round_trip(data_dir):
    s = config.load_settings()
    s.vinted_mode = "publish"
    config.save_settings(s)
    assert config.load_settings().vinted_mode == "publish"


def test_tutorial_defaults_for_old_settings_file(data_dir):
    paths.settings_file().write_text(json.dumps({"signature": "Merci !"}), encoding="utf-8")
    s = config.load_settings()
    assert s.tutorial.video_seen is False and s.tutorial.tours_seen == []


def test_tutorial_round_trip(data_dir):
    s = config.load_settings()
    s.tutorial = config.TutorialState(video_seen=True, tours_seen=["articles", "scenes"])
    config.save_settings(s)
    loaded = config.load_settings().tutorial
    assert loaded.video_seen is True and loaded.tours_seen == ["articles", "scenes"]
