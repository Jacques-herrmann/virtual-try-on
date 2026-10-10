"""Réception des fichiers envoyés par l'interface (photos, décors)."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import UploadFile
from PIL import Image

from vto.core.errors import VtoError
from vto.core.images import is_supported_image

MAX_BYTES = 30 * 1024 * 1024
CHUNK = 1024 * 1024


def _display_name(upload: UploadFile) -> str:
    return Path((upload.filename or "fichier").replace("\\", "/")).name


def _save(upload: UploadFile, target: Path) -> None:
    name = _display_name(upload)
    if not is_supported_image(name):
        raise VtoError(f"« {name} » n'est pas une image prise en charge (JPG, PNG, WEBP, AVIF).")
    written = 0
    with target.open("wb") as out:
        while chunk := upload.file.read(CHUNK):
            written += len(chunk)
            if written > MAX_BYTES:
                raise VtoError(f"« {name} » dépasse {MAX_BYTES // (1024 * 1024)} Mo.")
            out.write(chunk)
    try:
        with Image.open(target) as img:
            img.verify()
    except Exception as exc:
        raise VtoError(f"« {name} » est illisible ou n'est pas une image.") from exc


@contextmanager
def received_images(uploads: list[UploadFile]) -> Iterator[list[tuple[Path, str]]]:
    """Écrit les fichiers reçus dans un dossier temporaire après vérification.

    Donne des couples (chemin temporaire, nom d'origine) ; le dossier est supprimé ensuite.
    """
    with TemporaryDirectory(prefix="vto-upload-") as tmp:
        received = []
        for i, upload in enumerate(uploads, start=1):
            name = _display_name(upload)
            target = Path(tmp) / f"{i:03d}{Path(name).suffix.lower()}"
            _save(upload, target)
            received.append((target, name))
        yield received
