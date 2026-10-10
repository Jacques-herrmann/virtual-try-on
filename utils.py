import io
import os
import random
from PIL import Image as PILImage, ImageOps
from pathlib import Path

SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.webp', '.avif')

def load_image_as_pil(image_path: str) -> PILImage.Image:
    """Load and convert an image to PIL format."""
    img = PILImage.open(image_path).convert("RGB")
    return img


def pil_to_bytes(pil_image: PILImage.Image, format="JPEG", quality=95) -> bytes:
    """Convert a PIL image to bytes for API upload."""
    buffer = io.BytesIO()
    pil_image.save(buffer, format=format, quality=quality)
    return buffer.getvalue()



def resize_if_needed(img: PILImage.Image, max_size=1536) -> PILImage.Image:
    """Resize the image if it exceeds the max size while maintaining aspect ratio."""
    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        img = img.resize((new_w, new_h), PILImage.LANCZOS)
        print(f"    Redimensionnée : {w}x{h} → {new_w}x{new_h}")
    return img


def prepare_for_gemini(img: PILImage.Image) -> PILImage.Image:
    img = ImageOps.exif_transpose(img)

    if img.mode != "RGB":
        img = img.convert("RGB")

    buffer = io.BytesIO()
    img.save(buffer, format="WEBP", quality=90)
    buffer.seek(0)
    img = PILImage.open(buffer)
    img.load()

    return img


def get_random_item_from_folder(folder_path: str) -> str | None:
    """Get a random file path from a folder, filtering by supported formats."""
    files = [
        f for f in os.listdir(folder_path)
        if f.lower().endswith(SUPPORTED_FORMATS)
    ]
    if not files:
        return None
    selected_file = random.choice(files)
    return os.path.join(folder_path, selected_file)

def get_base_image_from_folder(folder_path: str) -> str | None:
    """Return the base of the image named base.* if it exists, otherwise a random image from the folder."""
    folder = Path(folder_path)
    results = list(folder.glob("base.*"))
    if results:
        return str(results[0])
    else:
        return get_random_item_from_folder(folder_path)

def get_item_info_if_exists(folder_path) -> str:
    """Check if a txt file exists in the folder and return its content."""
    folder = Path(folder_path)
    results = list(folder.glob("*.txt"))
    if results:
        with open(results[0], "r", encoding="utf-8") as f:
            return f.read()
    else:
        return ""