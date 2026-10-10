"""Scènes : un dossier de décors + un prompt modifiable par le client."""

import logging
import random
import shutil
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ValidationError

from vto.core import paths
from vto.core.errors import NoBackground
from vto.core.images import is_supported_image

log = logging.getLogger(__name__)

# Emplacement provisoire du pack livré ; le packaging (sous-projet 4) décidera du définitif.
DEFAULT_SCENES_SOURCE = Path(__file__).resolve().parents[4] / "default_scenes"


class SceneMeta(BaseModel):
    name: str
    enabled: bool = True
    order: int = 0


@dataclass(frozen=True)
class Scene:
    slug: str
    name: str
    enabled: bool
    order: int
    prompt: str
    backgrounds_dir: Path


def _images_in(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and is_supported_image(p))


def _has_any_background(backgrounds_dir: Path) -> bool:
    if not backgrounds_dir.is_dir():
        return False
    if _images_in(backgrounds_dir):
        return True
    return any(_images_in(sub) for sub in backgrounds_dir.iterdir() if sub.is_dir())


def _load_scene(folder: Path) -> Scene | None:
    prompt_file = folder / "prompt.md"
    backgrounds_dir = folder / "backgrounds"
    if not prompt_file.is_file():
        log.warning("Scène ignorée (pas de prompt.md) : %s", folder.name)
        return None
    if not _has_any_background(backgrounds_dir):
        log.warning("Scène ignorée (aucun décor) : %s", folder.name)
        return None
    try:
        meta_file = folder / "meta.json"
        meta = (
            SceneMeta.model_validate_json(meta_file.read_text(encoding="utf-8"))
            if meta_file.is_file()
            else SceneMeta(name=folder.name)
        )
    except (ValidationError, ValueError):
        log.warning("Scène ignorée (meta.json invalide) : %s", folder.name)
        return None
    return Scene(
        slug=folder.name,
        name=meta.name,
        enabled=meta.enabled,
        order=meta.order,
        prompt=prompt_file.read_text(encoding="utf-8"),
        backgrounds_dir=backgrounds_dir,
    )


def list_scenes(enabled_only: bool = True) -> list[Scene]:
    loaded = [_load_scene(d) for d in sorted(paths.scenes_dir().iterdir()) if d.is_dir()]
    found = [s for s in loaded if s and (s.enabled or not enabled_only)]
    return sorted(found, key=lambda s: (s.order, s.slug))


def pick_background(scene: Scene, garment_type: str, rng: random.Random | None = None) -> Path:
    """Tire un décor dans backgrounds/<type>/ s'il en contient, sinon à la racine."""
    rng = rng or random.Random()
    candidates = _images_in(scene.backgrounds_dir / garment_type) or _images_in(
        scene.backgrounds_dir
    )
    if not candidates:
        raise NoBackground(scene.name, garment_type)
    return rng.choice(candidates)


def render_prompt(scene: Scene, garment_type: str) -> str:
    return scene.prompt.replace("{garment_type}", garment_type)


def ensure_default_scenes(source: Path = DEFAULT_SCENES_SOURCE) -> bool:
    """Copie le pack par défaut si le client n'a encore aucune scène. Renvoie True si copié."""
    target = paths.scenes_dir()
    if any(target.iterdir()) or not source.is_dir():
        return False
    shutil.copytree(source, target, dirs_exist_ok=True)
    return True
