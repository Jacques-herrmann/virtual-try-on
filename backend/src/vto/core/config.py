"""Réglages utilisateur, stockés dans settings.json."""

import logging
import os
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from vto.core import paths

log = logging.getLogger(__name__)

# Modèles recommandés pour les nouveaux projets (doc Google AI, vérifiée le 2026-10-10).
DEFAULT_IMAGE_MODEL = "gemini-nano-banana-2.1"
DEFAULT_TEXT_MODEL = "gemini-3.8-flash"


def default_listing_prompt() -> str:
    return files("vto.core.prompts").joinpath("listing_default.md").read_text(encoding="utf-8")


class Settings(BaseModel):
    gemini_api_key: str | None = None
    image_model: str = DEFAULT_IMAGE_MODEL
    text_model: str = DEFAULT_TEXT_MODEL
    listing_prompt: str = Field(default_factory=default_listing_prompt)
    signature: str = ""
    vinted_mode: Literal["draft", "publish"] = "draft"

    def api_key(self) -> str | None:
        """Clé effective : GEMINI_API_KEY (développement, CI) prioritaire sur le fichier."""
        return os.environ.get("GEMINI_API_KEY") or self.gemini_api_key


def load_settings() -> Settings:
    file = paths.settings_file()
    if not file.exists():
        return Settings()
    try:
        return Settings.model_validate_json(file.read_text(encoding="utf-8"))
    except (ValidationError, ValueError):
        log.warning("settings.json illisible (%s), réglages par défaut utilisés", file)
        return Settings()


def save_settings(settings: Settings) -> None:
    file = paths.settings_file()
    tmp = file.with_suffix(".json.tmp")
    tmp.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp, file)
