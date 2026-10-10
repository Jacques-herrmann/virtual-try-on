"""Accès à Gemini via l'Interactions API (google-genai ≥ 2).

Le reste du cœur ne dépend que du protocole `GenAIClient` ; `GeminiClient` en est
l'implémentation réelle, les tests utilisent une doublure.
"""

import base64
import logging
import random
import time
from collections.abc import Callable, Sequence
from typing import Any, Protocol, TypeVar

import httpx
from PIL import Image
from pydantic import BaseModel, ValidationError

from vto.core import errors
from vto.core.images import to_jpeg_bytes

log = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)

IMAGE_ASPECT_RATIO = "3:4"
# Délai max d'une requête (s) : une image peut prendre une minute, au-delà on réessaie.
REQUEST_TIMEOUT = 180.0
RETRYABLE = (errors.TransientError, errors.NoImageReturned)


class GenAIClient(Protocol):
    def generate_image(self, model: str, prompt: str, images: Sequence[Image.Image]) -> bytes: ...

    def generate_json(
        self, model: str, prompt: str, images: Sequence[Image.Image], schema: type[M]
    ) -> M: ...


def map_sdk_error(exc: BaseException) -> errors.VtoError:
    """Traduit une erreur du SDK ou du réseau en erreur du cœur (par code HTTP)."""
    if isinstance(exc, httpx.TransportError) or type(exc).__name__ == "NoResponseError":
        return errors.TransientError()
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    message = str(getattr(exc, "message", "") or exc).lower()
    if status == 403 and "denied access" in message:
        return errors.ProjectBlocked()
    if status in (401, 403) or (status == 400 and "api key" in message):
        return errors.InvalidApiKey()
    if status == 404:
        return errors.ModelUnavailable()
    if status == 429:
        # Google renvoie 429 pour le débit comme pour le quota épuisé : on distingue au message.
        if "quota" in message and any(w in message for w in ("billing", "plan", "day", "limit: 0")):
            return errors.QuotaExceeded()
        return errors.TransientError()
    if isinstance(status, int) and status >= 500:
        return errors.TransientError()
    return errors.VtoError()


def with_retry[T](
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Réessaie `fn` sur les erreurs temporaires, avec un délai exponentiel ± 20 %."""
    for attempt in range(attempts):
        try:
            return fn()
        except RETRYABLE as exc:
            if attempt == attempts - 1:
                raise
            delay = base_delay * 2**attempt * random.uniform(0.8, 1.2)
            log.info("Erreur temporaire (%s), nouvel essai dans %.1f s", type(exc).__name__, delay)
            sleep(delay)
    raise AssertionError("inatteignable")


def _input(prompt: str, images: Sequence[Image.Image]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for img in images:
        parts.append(
            {
                "type": "image",
                "data": base64.b64encode(to_jpeg_bytes(img)).decode("ascii"),
                "mime_type": "image/jpeg",
            }
        )
    return parts


class GeminiClient:
    def __init__(self, api_key: str, *, sdk: Any = None, sleep=time.sleep):
        if sdk is None:
            from google import genai

            sdk = genai.Client(api_key=api_key)
        self._sdk = sdk
        self._sleep = sleep

    def _create(self, **kwargs) -> Any:
        try:
            return self._sdk.interactions.create(timeout=REQUEST_TIMEOUT, **kwargs)
        except errors.VtoError:
            raise
        except Exception as exc:
            log.warning("Erreur Gemini : %r", exc)
            raise map_sdk_error(exc) from exc

    def generate_image(self, model: str, prompt: str, images: Sequence[Image.Image]) -> bytes:
        def call() -> bytes:
            interaction = self._create(
                model=model,
                input=_input(prompt, images),
                response_format={"type": "image", "aspect_ratio": IMAGE_ASPECT_RATIO},
            )
            output = getattr(interaction, "output_image", None)
            if output is None or not output.data:
                text = getattr(interaction, "output_text", None)
                log.warning("Aucune image renvoyée. Texte : %s", text)
                raise errors.NoImageReturned()
            return base64.b64decode(output.data)

        return with_retry(call, sleep=self._sleep)

    def generate_json(
        self, model: str, prompt: str, images: Sequence[Image.Image], schema: type[M]
    ) -> M:
        def call() -> M:
            interaction = self._create(
                model=model,
                input=_input(prompt, images),
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": schema.model_json_schema(),
                },
            )
            text = getattr(interaction, "output_text", None) or ""
            try:
                return schema.model_validate_json(text)
            except ValidationError as exc:
                log.warning("Sortie JSON invalide : %s", text[:500])
                raise errors.InvalidModelOutput() from exc

        return with_retry(call, sleep=self._sleep)
