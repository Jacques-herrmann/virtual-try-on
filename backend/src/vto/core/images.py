"""Utilitaires d'image (Pillow ≥ 11.3, qui lit l'AVIF nativement)."""

import io
from pathlib import Path

from PIL import Image, ImageOps

SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".avif")
MAX_SIZE = 1536


def is_supported_image(path: str | Path) -> bool:
    return str(path).lower().endswith(SUPPORTED_EXTENSIONS)


def load_image(path: str | Path) -> Image.Image:
    """Charge une image, applique l'orientation EXIF et convertit en RGB."""
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        return img.convert("RGB")


def resize_max(img: Image.Image, max_size: int = MAX_SIZE) -> Image.Image:
    """Réduit l'image si son plus grand côté dépasse `max_size`, en gardant le ratio."""
    w, h = img.size
    if max(w, h) <= max_size:
        return img
    ratio = max_size / max(w, h)
    return img.resize((round(w * ratio), round(h * ratio)), Image.Resampling.LANCZOS)


def to_jpeg_bytes(img: Image.Image, quality: int = 90) -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def save_jpeg(img: Image.Image, path: Path, quality: int = 95) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, format="JPEG", quality=quality)
