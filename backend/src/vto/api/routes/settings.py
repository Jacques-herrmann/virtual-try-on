from fastapi import APIRouter, Request
from pydantic import BaseModel

from vto.core import config, pipeline
from vto.core.errors import VtoError

router = APIRouter(prefix="/api/settings")


class SettingsView(BaseModel):
    """Réglages renvoyés à l'interface : jamais la clé, seulement ses 4 derniers caractères."""

    has_key: bool
    key_hint: str | None
    signature: str
    listing_prompt: str
    image_model: str
    text_model: str


class SettingsUpdate(BaseModel):
    signature: str | None = None
    listing_prompt: str | None = None
    image_model: str | None = None
    text_model: str | None = None


class KeyCheck(BaseModel):
    key: str


def _view(settings: config.Settings) -> SettingsView:
    key = settings.api_key()
    return SettingsView(
        has_key=bool(key),
        key_hint=key[-4:] if key else None,
        signature=settings.signature,
        listing_prompt=settings.listing_prompt,
        image_model=settings.image_model,
        text_model=settings.text_model,
    )


@router.get("")
def get_settings() -> SettingsView:
    return _view(config.load_settings())


@router.put("")
def update_settings(update: SettingsUpdate) -> SettingsView:
    settings = config.load_settings()
    changes = update.model_dump(exclude_none=True)
    for field in ("image_model", "text_model"):
        if field in changes:
            changes[field] = changes[field].strip()
            if not changes[field]:
                raise VtoError("Le nom du modèle ne peut pas être vide.")
    settings = settings.model_copy(update=changes)
    config.save_settings(settings)
    return _view(settings)


@router.post("/reset-listing-prompt")
def reset_listing_prompt() -> SettingsView:
    settings = config.load_settings()
    settings.listing_prompt = config.default_listing_prompt()
    config.save_settings(settings)
    return _view(settings)


@router.post("/check-key")
def check_key(request: Request, body: KeyCheck) -> SettingsView:
    """Vérifie la clé auprès de Gemini ; l'enregistre et relance la file si elle est valide."""
    settings = config.load_settings()
    factory = request.app.state.client_factory or pipeline.GeminiClient
    pipeline.verify_api_key(body.key, settings, factory)
    settings.gemini_api_key = body.key.strip()
    config.save_settings(settings)
    request.app.state.queue.resume()
    return _view(settings)
