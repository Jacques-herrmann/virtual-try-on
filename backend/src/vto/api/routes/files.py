"""Images des articles et des scènes (uniquement des images, jamais les fichiers d'état)."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from vto.core import paths
from vto.core.images import is_supported_image

router = APIRouter(prefix="/files")


def _image(base: Path, folder: str, rel: str) -> FileResponse:
    root = paths.safe_join(base, folder)
    target = paths.safe_join(root, rel) if root is not None else None
    if target is None or not is_supported_image(target) or not target.is_file():
        raise HTTPException(404)
    # Une image régénérée garde son nom : le navigateur doit revalider à chaque fois.
    return FileResponse(target, headers={"Cache-Control": "no-cache"})


@router.get("/articles/{article_id}/{rel:path}")
def article_file(article_id: str, rel: str) -> FileResponse:
    return _image(paths.articles_dir(), article_id, rel)


@router.get("/scenes/{slug}/{rel:path}")
def scene_file(slug: str, rel: str) -> FileResponse:
    return _image(paths.scenes_dir(), slug, rel)
