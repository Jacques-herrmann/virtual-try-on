"""Import unique des données du prototype (dossier « batch »).

    python -m vto.tools.import_legacy <dossier_batch> [--as-default-pack <dossier_cible>]

Préfixes du prototype : c = chaussures, f = femme, h = homme. Sous-dossiers de décors :
1 = scène mannequin, 2 = scène cintre. Le dossier source n'est jamais modifié.
"""

import argparse
import logging
from pathlib import Path

from vto.core import config, paths, scenes, storage
from vto.core.images import is_supported_image, load_image, resize_max, save_jpeg
from vto.core.models import Article, UserInput

log = logging.getLogger(__name__)

PREFIX_FOLDERS = {"c": "chaussures", "f": "femme", "h": "homme"}
SCENE_BY_INDEX = {"1": "mannequin", "2": "cintre"}

LEGACY_SIGNATURE = (
    "Petit rappel : Abonne-toi à mon profil pour bénéficier de -10% de remise immédiate ! "
    "Et si tu es ravi(e) de ton achat, un petit commentaire te fera gagner -10% "
    "supplémentaires sur ta prochaine pépite !"
)

# Mots-clés du nom de dossier → type de vêtement (premier trouvé).
TYPE_KEYWORDS = {
    "robe": "robe",
    "jupe": "jupe",
    "pull": "haut", "sweat": "haut", "tshirt": "haut", "t-shirt": "haut", "top": "haut",
    "chemise": "haut", "blouse": "haut", "gilet": "haut", "debardeur": "haut",
    "pantalon": "pantalon", "jean": "pantalon", "short": "pantalon", "legging": "pantalon",
    "veste": "veste", "manteau": "veste", "blouson": "veste", "doudoune": "veste",
    "sac": "sac",
    "chaussure": "chaussures", "basket": "chaussures", "botte": "chaussures",
}


def guess_input(folder_name: str, notes: str | None) -> UserInput:
    prefix, _, rest = folder_name.partition("_")
    words = rest.lower().replace("-", "_").split("_")
    if prefix == "c":
        return UserInput(garment_type="chaussures", notes=notes)
    garment_type = next((TYPE_KEYWORDS[w] for w in words if w in TYPE_KEYWORDS), "autre")
    audience = PREFIX_FOLDERS.get(prefix) if prefix in ("f", "h") else None
    return UserInput(garment_type=garment_type, audience=audience, notes=notes)


def import_backgrounds(batch: Path, scenes_root: Path) -> int:
    """Copie (réduits à 1536 px, en JPEG) les décors vers <scène>/backgrounds/<dossier>/."""
    count = 0
    for prefix, folder in PREFIX_FOLDERS.items():
        for index, scene_slug in SCENE_BY_INDEX.items():
            source = batch / "input" / "backgrounds" / prefix / index
            if not source.is_dir():
                continue
            target = scenes_root / scene_slug / "backgrounds" / folder
            for image in sorted(source.iterdir()):
                if image.is_file() and is_supported_image(image):
                    save_jpeg(resize_max(load_image(image)), target / f"{image.stem}.jpg", 90)
                    count += 1
    return count


def import_clothes(batch: Path) -> list[Article]:
    articles = []
    clothes = batch / "input" / "clothes"
    if not clothes.is_dir():
        return articles
    for folder in sorted(d for d in clothes.iterdir() if d.is_dir()):
        photos = sorted(p for p in folder.iterdir() if p.is_file() and is_supported_image(p))
        photos.sort(key=lambda p: p.stem.lower() != "base")  # base.* en premier
        if not photos:
            log.warning("Aucune photo dans %s, ignoré", folder.name)
            continue
        texts = sorted(folder.glob("*.txt"))
        notes = (texts[0].read_text(encoding="utf-8").strip() or None) if texts else None
        articles.append(storage.create_article(guess_input(folder.name, notes), photos))
    return articles


def import_into_user_data(batch: Path) -> tuple[int, list[Article]]:
    scenes.ensure_default_scenes()
    n_backgrounds = import_backgrounds(batch, paths.scenes_dir())
    articles = import_clothes(batch)
    settings = config.load_settings()
    if not settings.signature:
        settings.signature = LEGACY_SIGNATURE
        config.save_settings(settings)
    return n_backgrounds, articles


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("batch", type=Path, help="dossier batch du prototype")
    parser.add_argument(
        "--as-default-pack",
        type=Path,
        metavar="DOSSIER",
        help="écrit seulement les décors dans ce dossier (ex. default_scenes du dépôt)",
    )
    args = parser.parse_args(argv)
    if args.as_default_pack:
        n = import_backgrounds(args.batch, args.as_default_pack)
        print(f"{n} décor(s) écrits dans {args.as_default_pack}")
        return
    n, articles = import_into_user_data(args.batch)
    print(f"{n} décor(s) et {len(articles)} article(s) importés dans {paths.data_dir()}")


if __name__ == "__main__":
    main()
