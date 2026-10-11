"""Doublures de test pour le client Gemini."""

from collections import deque
from dataclasses import dataclass, field

from PIL import Image

from vto.core.images import to_jpeg_bytes


def png_bytes(color="green") -> bytes:
    return to_jpeg_bytes(Image.new("RGB", (30, 40), color))


@dataclass
class Call:
    kind: str
    model: str
    prompt: str
    n_images: int
    schema: type | None = None


@dataclass
class FakeClient:
    """Réponses scriptées : chaque élément est un résultat ou une exception à lever."""

    image_responses: deque = field(default_factory=deque)
    json_responses: deque = field(default_factory=deque)
    calls: list[Call] = field(default_factory=list)
    default_image: bytes = field(default_factory=png_bytes)
    check_error: BaseException | None = None
    checked: list[list[str]] = field(default_factory=list)

    def _next(self, queue, default):
        item = queue.popleft() if queue else default
        if isinstance(item, BaseException):
            raise item
        return item

    def generate_image(self, model, prompt, images):
        self.calls.append(Call("image", model, prompt, len(images)))
        return self._next(self.image_responses, self.default_image)

    def generate_json(self, model, prompt, images, schema):
        self.calls.append(Call("json", model, prompt, len(images), schema))
        item = self._next(self.json_responses, None)
        if item is None:
            raise AssertionError("aucune réponse JSON scriptée")
        # Comme le vrai client : une instance du schéma demandé, validée par lui.
        return schema.model_validate(item.model_dump())

    def check_models(self, models):
        self.checked.append(list(models))
        if self.check_error is not None:
            raise self.check_error
