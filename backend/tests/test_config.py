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
