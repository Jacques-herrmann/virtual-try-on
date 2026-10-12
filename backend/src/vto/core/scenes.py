"""Scènes : un dossier de décors + un prompt modifiable par le client."""

import logging
import random
import re
import shutil
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import get_args

from pydantic import BaseModel, ValidationError

from vto.core import paths
from vto.core.errors import NoBackground, VtoError
from vto.core.images import is_supported_image
from vto.core.models import Audience, GarmentType

log = logging.getLogger(__name__)


def default_scenes_source() -> Path:
    """Pack de scènes livré avec l'app (données du paquet `vto.core`)."""
    # Toujours un vrai dossier : installation éditable, wheel ou exécutable PyInstaller.
    return Path(str(files("vto.core").joinpath("default_scenes")))


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


def _read_meta(folder: Path) -> SceneMeta | None:
    """Métadonnées de la scène ; défauts si meta.json absent, None s'il est invalide."""
    meta_file = folder / "meta.json"
    if not meta_file.is_file():
        return SceneMeta(name=folder.name)
    try:
        return SceneMeta.model_validate_json(meta_file.read_text(encoding="utf-8"))
    except (ValidationError, ValueError):
        return None


def _problem(folder: Path, meta: SceneMeta | None) -> str | None:
    if not (folder / "prompt.md").is_file():
        return "prompt.md manquant"
    if not _has_any_background(folder / "backgrounds"):
        return "aucun décor"
    if meta is None:
        return "meta.json invalide"
    return None


def _load_scene(folder: Path) -> Scene | None:
    meta = _read_meta(folder)
    problem = _problem(folder, meta)
    if problem:
        log.warning("Scène ignorée (%s) : %s", problem, folder.name)
        return None
    return Scene(
        slug=folder.name,
        name=meta.name,
        enabled=meta.enabled,
        order=meta.order,
        prompt=(folder / "prompt.md").read_text(encoding="utf-8"),
        backgrounds_dir=folder / "backgrounds",
    )


def list_scenes(enabled_only: bool = True) -> list[Scene]:
    loaded = [_load_scene(d) for d in sorted(paths.scenes_dir().iterdir()) if d.is_dir()]
    found = [s for s in loaded if s and (s.enabled or not enabled_only)]
    return sorted(found, key=lambda s: (s.order, s.slug))


def pick_background(
    scene: Scene, keys: Sequence[str | None], rng: random.Random | None = None
) -> Path:
    """Tire un décor dans le premier sous-dossier non vide parmi `keys`, sinon à la racine.

    Ex. keys = (type, public) : backgrounds/chaussures/, puis backgrounds/femme/, puis racine.
    """
    rng = rng or random.Random()
    for folder in [scene.backgrounds_dir / k for k in keys if k] + [scene.backgrounds_dir]:
        candidates = _images_in(folder)
        if candidates:
            return rng.choice(candidates)
    raise NoBackground(scene.name, " / ".join(k for k in keys if k))


def render_prompt(scene: Scene, garment_type: str) -> str:
    return scene.prompt.replace("{garment_type}", garment_type)


def ensure_default_scenes(source: Path | None = None) -> bool:
    """Copie le pack par défaut si le client n'a encore aucune scène. Renvoie True si copié."""
    source = source or default_scenes_source()
    target = paths.scenes_dir()
    if any(target.iterdir()) or not source.is_dir():
        return False
    shutil.copytree(source, target, dirs_exist_ok=True)
    return True


# --- Gestion des scènes depuis l'interface -------------------------------------------------

BACKGROUND_SUBFOLDERS = frozenset(get_args(GarmentType)) | frozenset(get_args(Audience))


@dataclass(frozen=True)
class SceneInfo:
    """Vue d'une scène pour l'interface, y compris inutilisable (`problem` explique pourquoi)."""

    slug: str
    name: str
    enabled: bool
    order: int
    problem: str | None


def _scene_folders() -> list[Path]:
    return sorted(d for d in paths.scenes_dir().iterdir() if d.is_dir())


def list_scene_infos() -> list[SceneInfo]:
    found = []
    for folder in _scene_folders():
        meta = _read_meta(folder)
        found.append(
            SceneInfo(
                slug=folder.name,
                name=meta.name if meta else folder.name,
                enabled=meta.enabled if meta else False,
                order=meta.order if meta else 0,
                problem=_problem(folder, meta),
            )
        )
    return sorted(found, key=lambda i: (i.problem == "meta.json invalide", i.order, i.slug))


def _scene_dir(slug: str) -> Path:
    folder = paths.safe_join(paths.scenes_dir(), slug)
    if folder is None or folder.parent != paths.scenes_dir().resolve() or not folder.is_dir():
        raise VtoError("Scène introuvable.")
    return folder


def _slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "scene"


def _write_meta(folder: Path, meta: SceneMeta) -> None:
    (folder / "meta.json").write_text(meta.model_dump_json(indent=2), encoding="utf-8")


def _clean_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise VtoError("Donne un nom à la scène.")
    return name


def scene_info(slug: str) -> SceneInfo:
    _scene_dir(slug)
    return next(i for i in list_scene_infos() if i.slug == slug)


def create_scene(name: str) -> SceneInfo:
    name = _clean_name(name)
    base = _slugify(name)
    slug, n = base, 1
    while (paths.scenes_dir() / slug).exists():
        n += 1
        slug = f"{base}-{n}"
    folder = paths.scenes_dir() / slug
    (folder / "backgrounds").mkdir(parents=True)
    template = files("vto.core.prompts").joinpath("scene_template.md").read_text(encoding="utf-8")
    (folder / "prompt.md").write_text(template, encoding="utf-8")
    last = max((i.order for i in list_scene_infos() if i.slug != slug), default=0)
    _write_meta(folder, SceneMeta(name=name, order=last + 1))
    return scene_info(slug)


def get_prompt(slug: str) -> str:
    prompt_file = _scene_dir(slug) / "prompt.md"
    return prompt_file.read_text(encoding="utf-8") if prompt_file.is_file() else ""


def update_scene(
    slug: str,
    *,
    name: str | None = None,
    enabled: bool | None = None,
    order: int | None = None,
    prompt: str | None = None,
) -> SceneInfo:
    folder = _scene_dir(slug)
    meta = _read_meta(folder) or SceneMeta(name=slug)
    if name is not None:
        meta.name = _clean_name(name)
    if enabled is not None:
        meta.enabled = enabled
    if order is not None:
        meta.order = order
    _write_meta(folder, meta)
    if prompt is not None:
        (folder / "prompt.md").write_text(prompt, encoding="utf-8")
    return scene_info(slug)


def delete_scene(slug: str) -> None:
    """Suppression explicite, après confirmation du client."""
    shutil.rmtree(_scene_dir(slug))


def list_backgrounds(slug: str) -> list[str]:
    backgrounds = _scene_dir(slug) / "backgrounds"
    found = [p.name for p in _images_in(backgrounds)]
    if backgrounds.is_dir():
        for sub in sorted(d for d in backgrounds.iterdir() if d.is_dir()):
            found += [f"{sub.name}/{p.name}" for p in _images_in(sub)]
    return found


def add_background(
    slug: str, source: Path, subfolder: str | None, filename: str | None = None
) -> str:
    """Copie `source` dans les décors (racine ou sous-dossier type/public) ; renvoie le chemin."""
    if subfolder is not None and subfolder not in BACKGROUND_SUBFOLDERS:
        raise VtoError(f"Sous-dossier de décor inconnu : « {subfolder} ».")
    name = Path((filename or source.name).replace("\\", "/")).name
    if not is_supported_image(name):
        raise VtoError("Ce fichier n'est pas une image prise en charge (JPG, PNG, WEBP, AVIF).")
    target_dir = _scene_dir(slug) / "backgrounds"
    if subfolder:
        target_dir /= subfolder
    target_dir.mkdir(parents=True, exist_ok=True)
    stem, suffix = Path(name).stem, Path(name).suffix
    target, n = target_dir / name, 1
    while target.exists():
        n += 1
        target = target_dir / f"{stem}-{n}{suffix}"
    shutil.copy2(source, target)
    return f"{subfolder}/{target.name}" if subfolder else target.name


def delete_background(slug: str, rel_path: str) -> None:
    """Suppression explicite d'un décor, après confirmation du client."""
    target = paths.safe_join(_scene_dir(slug) / "backgrounds", rel_path)
    if target is None or not target.is_file() or not is_supported_image(target):
        raise VtoError("Décor introuvable.")
    target.unlink()
