from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile
from pydantic import BaseModel

from vto.api.uploads import received_images
from vto.core import scenes
from vto.core.errors import VtoError

router = APIRouter(prefix="/api/scenes")


class SceneView(BaseModel):
    slug: str
    name: str
    enabled: bool
    order: int
    problem: str | None


class SceneDetail(SceneView):
    prompt: str
    backgrounds: list[str]


class SceneCreate(BaseModel):
    name: str


class SceneUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    order: int | None = None
    prompt: str | None = None


def _detail(slug: str) -> SceneDetail:
    return SceneDetail(
        **asdict(scenes.scene_info(slug)),
        prompt=scenes.get_prompt(slug),
        backgrounds=scenes.list_backgrounds(slug),
    )


@router.get("")
def list_scenes() -> list[SceneView]:
    return [SceneView(**asdict(info)) for info in scenes.list_scene_infos()]


@router.post("", status_code=201)
def create_scene(body: SceneCreate) -> SceneDetail:
    return _detail(scenes.create_scene(body.name).slug)


@router.get("/{slug}")
def get_scene(slug: str) -> SceneDetail:
    return _detail(slug)


@router.patch("/{slug}")
def update_scene(slug: str, body: SceneUpdate) -> SceneDetail:
    scenes.update_scene(slug, **body.model_dump(exclude_none=True))
    return _detail(slug)


@router.delete("/{slug}", status_code=204)
def delete_scene(slug: str) -> Response:
    scenes.delete_scene(slug)
    return Response(status_code=204)


@router.post("/{slug}/backgrounds")
def add_backgrounds(
    slug: str,
    files: Annotated[list[UploadFile] | None, File()] = None,
    subfolder: Annotated[str | None, Form()] = None,
) -> SceneDetail:
    if not files:
        raise VtoError("Ajoute au moins une image de décor.")
    scenes.scene_info(slug)  # scène introuvable : erreur avant de lire les fichiers
    with received_images(files) as received:
        for path, name in received:
            scenes.add_background(slug, path, subfolder or None, filename=name)
    return _detail(slug)


@router.delete("/{slug}/backgrounds/{rel:path}", status_code=204)
def delete_background(slug: str, rel: str) -> Response:
    scenes.delete_background(slug, rel)
    return Response(status_code=204)
