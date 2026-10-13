"""`vto-tutorial` : vidéos du tutoriel de première ouverture (spec 2026-10-13-tutorial-design).

    vto-tutorial capture     une fois, avec GEMINI_API_KEY : génère et enregistre la démo
                             (--from-article : reprend un article déjà généré dans l'app)
    vto-tutorial record      rejoue la démo dans l'app et filme (sans réseau)
    vto-tutorial edit-key    monte la vidéo « clé Gemini » enregistrée à la main

À lancer depuis la racine du dépôt (données dans tools/tutorial, sortie dans
frontend/public/tutorial).
"""

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

from vto.tools.tutorial import captions, video
from vto.tools.tutorial.scenario import Demo, Director, full, short

SIZE = {"width": 1280, "height": 800}
# Erreurs prévues (données ou outil manquants) : message seul, sans pile d'appels.
USER_ERRORS = {"MissingCapture", "MissingFront", "MissingFfmpeg", "CaptureError"}
CURSOR = Path(__file__).with_name("cursor.js")


def _load_env(file: Path = Path(".env")) -> None:
    """Variables du fichier .env (GEMINI_API_KEY), sans écraser celles déjà définies."""
    if not file.is_file():
        return
    for line in file.read_text(encoding="utf-8").splitlines():
        name, sep, value = line.partition("=")
        if sep and name.strip() and not name.lstrip().startswith("#"):
            os.environ.setdefault(name.strip(), value.strip().strip('"'))


def _launch(playwright):
    try:
        return playwright.chromium.launch(channel="chrome")
    except Exception:
        return playwright.chromium.launch()


def record(base: Path, out: Path, *, short_version: bool, price: str, delay: float) -> Path:
    """Filme le scénario ; écrit kaloe.mp4, kaloe.vtt et kaloe.jpg dans `out`."""
    from playwright.sync_api import sync_playwright

    from vto.tools.tutorial.capture import demo_input, demo_photos
    from vto.tools.tutorial.harness import running_app

    if short_version:
        demo = Demo(photo=Path(), garment_type="robe", audience="femme", price=price)
    else:
        user_input = demo_input(base / "demo")
        draft = base / "vinted-draft.png"
        demo = Demo(
            photo=demo_photos(base / "demo")[0],
            garment_type=user_input.garment_type,
            audience=user_input.audience or "femme",
            price=price,
            draft_image=draft if draft.is_file() else None,
        )
        if demo.draft_image is None:
            print(f"(pas de {draft} : la vidéo s'arrête sans le plan du brouillon Vinted)")

    # Ordre de sortie : le navigateur se ferme avant la suppression de la vidéo brute.
    with (
        tempfile.TemporaryDirectory(prefix="kaloe-video-", ignore_cleanup_errors=True) as raw_dir,
        running_app(base / "capture", delay=delay, fill_seconds=2.5) as url,
        sync_playwright() as playwright,
    ):
        browser = _launch(playwright)
        context = browser.new_context(
            viewport=SIZE, record_video_dir=raw_dir, record_video_size=SIZE, locale="fr-FR"
        )
        context.add_init_script(path=str(CURSOR))
        page = context.new_page()
        t0 = time.monotonic()
        page.goto(url)
        page.get_by_text("Ajoute ton premier vêtement").wait_for()
        trim = time.monotonic() - t0  # écran blanc et chargement : coupés au montage

        director = Director(page, t0)
        (short if short_version else full)(director, demo)
        director.wait(1.0)

        raw = Path(page.video.path())
        context.close()
        browser.close()

        mp4 = out / "kaloe.mp4"
        video.finalize(raw, mp4, out / "kaloe.jpg", trim=trim)
    (out / "kaloe.vtt").write_text(captions.to_webvtt(director.cues, offset=trim), encoding="utf-8")
    return mp4


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="vto-tutorial", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=Path("tools/tutorial"),
                        help="dossier demo/, capture/, vinted-draft.png")
    parser.add_argument("--out", type=Path, default=Path("frontend/public/tutorial"))
    commands = parser.add_subparsers(dest="command", required=True)
    cap = commands.add_parser("capture", help="génère la démo avec le vrai Gemini (une fois)")
    cap.add_argument("--from-article", metavar="ID_OU_MOT",
                     help="reprend un article déjà généré dans l'app (identifiant ou mot du titre)")
    rec = commands.add_parser("record", help="filme la démo dans l'app (sans réseau)")
    rec.add_argument("--short", action="store_true", help="deux étapes seulement (test)")
    rec.add_argument("--price", default="15", help="prix saisi à la relecture")
    rec.add_argument("--delay", type=float, default=2.5, help="durée d'une génération rejouée (s)")
    key = commands.add_parser("edit-key", help="monte la vidéo « clé Gemini »")
    key.add_argument("source", type=Path)
    key.add_argument("--crop", type=video.Box.parse, help="x,y,w,h")
    key.add_argument("--blur", type=video.Blur.parse, action="append", default=[],
                     help="x,y,w,h ou x,y,w,h@début-fin (secondes), répétable")
    args = parser.parse_args(argv)

    try:
        if args.command == "capture":
            from vto.tools.tutorial.capture import capture, capture_from_article

            demo, out = args.data / "demo", args.data / "capture"
            if args.from_article:
                print(capture_from_article(args.from_article, demo, out))
            else:
                _load_env()
                print(capture(demo, out))
        elif args.command == "record":
            mp4 = record(args.data, args.out, short_version=args.short, price=args.price,
                         delay=args.delay)
            print(f"Vidéo : {mp4} ({mp4.stat().st_size // 1024} Ko)")
        else:
            target = args.out / "cle-gemini.mp4"
            video.edit(args.source, target, crop=args.crop, blurs=args.blur)
            print(f"Vidéo : {target} ({target.stat().st_size // 1024} Ko)")
    except Exception as exc:
        if type(exc).__name__ in USER_ERRORS:
            sys.exit(str(exc))
        raise
