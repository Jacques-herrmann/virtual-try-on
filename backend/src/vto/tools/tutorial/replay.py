"""Client Gemini enregistreur (une fois, avec le vrai Gemini) et rejoueur (tournage, sans réseau).

Les images sont rangées par empreinte du prompt : il dépend seulement de la scène et du type
de vêtement, pas du décor tiré au hasard.
"""

import hashlib
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

LISTING = "listing.json"
IMAGES = "images"
SIGNATURES = ((b"\x89PNG", ".png"), (b"\xff\xd8", ".jpg"))


class MissingCapture(Exception):
    pass


def _key(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def _suffix(data: bytes) -> str:
    """Extension réelle, pour ouvrir les images enregistrées et les valider à l'œil."""
    for signature, suffix in SIGNATURES:
        if data.startswith(signature):
            return suffix
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return ".bin"


def save_image(folder: Path, prompt: str, data: bytes) -> Path:
    target = folder / IMAGES / f"{_key(prompt)}{_suffix(data)}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def save_listing(folder: Path, listing: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / LISTING).write_text(
        json.dumps(listing, ensure_ascii=False, indent=2), encoding="utf-8"
    )


@dataclass
class RecordingClient:
    """Enveloppe le vrai client et garde ses réponses dans `folder`."""

    inner: object
    folder: Path

    def generate_image(self, model: str, prompt: str, images: Sequence) -> bytes:
        data = self.inner.generate_image(model, prompt, images)
        save_image(self.folder, prompt, data)
        return data

    def generate_json(self, model: str, prompt: str, images: Sequence, schema):
        output = self.inner.generate_json(model, prompt, images, schema)
        save_listing(self.folder, output.model_dump(mode="json"))
        return output

    def check_models(self, models: Sequence[str]) -> None:
        self.inner.check_models(models)


class ReplayClient:
    """Rend les réponses enregistrées après `delay` secondes, comme une vraie génération."""

    def __init__(self, folder: Path, delay: float = 2.0):
        if not (folder / LISTING).is_file():
            raise MissingCapture(
                f"Aucune donnée de tournage dans {folder} : lancer d'abord `vto-tutorial capture`."
            )
        self.folder = folder
        self.delay = delay

    def generate_image(self, model: str, prompt: str, images: Sequence) -> bytes:
        time.sleep(self.delay)
        found = sorted((self.folder / IMAGES).glob(f"{_key(prompt)}.*"))
        if not found:
            raise MissingCapture(f"Pas d'image enregistrée pour cette scène ({_key(prompt)}).")
        return found[0].read_bytes()

    def generate_json(self, model: str, prompt: str, images: Sequence, schema):
        time.sleep(self.delay)
        return schema.model_validate_json((self.folder / LISTING).read_text(encoding="utf-8"))

    def check_models(self, models: Sequence[str]) -> None:
        pass
