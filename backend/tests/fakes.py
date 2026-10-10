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


@dataclass
class FakeClient:
    """Réponses scriptées : chaque élément est un résultat ou une exception à lever."""

    image_responses: deque = field(default_factory=deque)
    json_responses: deque = field(default_factory=deque)
    calls: list[Call] = field(default_factory=list)
    default_image: bytes = field(default_factory=png_bytes)

    def _next(self, queue, default):
        item = queue.popleft() if queue else default
        if isinstance(item, BaseException):
            raise item
        return item

    def generate_image(self, model, prompt, images):
        self.calls.append(Call("image", model, prompt, len(images)))
        return self._next(self.image_responses, self.default_image)

    def generate_json(self, model, prompt, images, schema):
        self.calls.append(Call("json", model, prompt, len(images)))
        item = self._next(self.json_responses, None)
        if item is None:
            raise AssertionError("aucune réponse JSON scriptée")
        return item
