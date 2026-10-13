"""CLI de développement : utiliser le cœur sans interface graphique."""

import functools
import json
import shutil
from pathlib import Path
from typing import Annotated

import typer

from vto.core import config, errors, paths, pipeline, scenes, storage
from vto.core.images import load_image, save_jpeg
from vto.core.logging import setup_logging
from vto.core.models import Article, ArticleStatus, UserInput

app = typer.Typer(no_args_is_help=True, help="Kaloé : photos portées et annonces Vinted.")
config_app = typer.Typer(no_args_is_help=True, help="Réglages.")
app.add_typer(config_app, name="config")


def get_client(settings: config.Settings):
    """Point d'injection pour les tests."""
    return pipeline.build_client(settings)


@app.callback()
def _startup() -> None:
    setup_logging()
    scenes.ensure_default_scenes()


def handle_errors(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except errors.VtoError as exc:
            typer.echo(f"Erreur : {exc.user_message}", err=True)
            raise typer.Exit(1) from exc

    return wrapper


def _progress(article_id: str, step: str, detail: str) -> None:
    if step == "scene":
        typer.echo(f"  image « {detail} » terminée")
    elif step == "listing":
        typer.echo("  annonce terminée")


def _summary(article: Article) -> str:
    title = article.listing.title if article.listing else "-"
    return f"{article.id}  {article.status.value:<10}  {article.input.garment_type:<10}  {title}"


@config_app.command("set-key")
@handle_errors
def set_key(key: str) -> None:
    """Enregistre la clé API Gemini."""
    settings = config.load_settings()
    settings.gemini_api_key = key
    config.save_settings(settings)
    typer.echo("Clé enregistrée.")


@app.command()
@handle_errors
def add(
    photos: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False)],
    garment_type: Annotated[str, typer.Option("--type", help="robe, haut, chaussures…")],
    audience: Annotated[str | None, typer.Option(help="femme, homme ou enfant")] = None,
    brand: str | None = None,
    size: str | None = None,
    condition: str | None = None,
    color: str | None = None,
    price: float | None = None,
    notes: str | None = None,
) -> None:
    """Ajoute un article à partir d'une ou plusieurs photos."""
    try:
        user_input = UserInput(
            garment_type=garment_type, audience=audience, brand=brand, size=size,
            condition=condition,
            color=color, price=price, notes=notes,
        )
    except ValueError as exc:
        raise errors.VtoError(f"Saisie invalide : {exc}") from exc
    article = storage.create_article(user_input, photos)
    typer.echo(article.id)


@app.command("list")
@handle_errors
def list_cmd() -> None:
    """Liste les articles."""
    for article in storage.list_articles():
        typer.echo(_summary(article))


@app.command()
@handle_errors
def run(ids: Annotated[list[str] | None, typer.Argument()] = None) -> None:
    """Traite les articles en brouillon (ou ceux passés en argument)."""
    settings = config.load_settings()
    if not ids:
        ids = [a.id for a in storage.list_articles() if a.status == ArticleStatus.DRAFT]
    if not ids:
        typer.echo("Aucun article à traiter.")
        return
    client = get_client(settings)
    for i, article_id in enumerate(ids, start=1):
        typer.echo(f"[{i}/{len(ids)}] {article_id}")
        article = pipeline.process_article(
            article_id, client=client, settings=settings, on_progress=_progress
        )
        typer.echo(f"  → {article.status.value}" + (f" : {article.error}" if article.error else ""))


@app.command()
@handle_errors
def regen(
    article_id: str,
    scene: Annotated[list[str] | None, typer.Option(help="Scène à régénérer (répétable)")] = None,
    listing: Annotated[bool, typer.Option("--listing", help="Régénère l'annonce")] = False,
) -> None:
    """Régénère des images et/ou l'annonce d'un article."""
    settings = config.load_settings()
    client = get_client(settings)
    article = pipeline.process_article(
        article_id,
        client=client,
        settings=settings,
        scene_slugs=scene or [],
        regenerate_listing=listing,
        on_progress=_progress,
    )
    typer.echo(f"→ {article.status.value}")


@app.command()
@handle_errors
def show(article_id: str) -> None:
    """Affiche l'annonce et les images d'un article."""
    article = storage.load(article_id)
    folder = paths.article_dir(article.id)
    typer.echo(_summary(article))
    if article.error:
        typer.echo(f"Erreur : {article.error}")
    for result in article.scenes:
        where = folder / result.image if result.image else result.error
        typer.echo(f"  {result.scene:<12} {result.status:<7} {where}")
    if article.listing:
        typer.echo(article.listing.model_dump_json(indent=2))


def export_article(article: Article, target: Path) -> None:
    """Images numérotées (scènes puis photos d'origine) + description.json."""
    source = paths.article_dir(article.id)
    target.mkdir(parents=True, exist_ok=True)
    images = [r.image for r in article.scenes if r.status == "ok" and r.image] + article.photos
    for i, rel in enumerate(images):
        out = target / f"{i:02d}.jpg"
        if rel.lower().endswith((".jpg", ".jpeg")):
            shutil.copy2(source / rel, out)
        else:
            save_jpeg(load_image(source / rel), out)
    listing = article.listing.model_dump() if article.listing else {}
    (target / "description.json").write_text(
        json.dumps(listing, ensure_ascii=False, indent=2), encoding="utf-8"
    )


@app.command()
@handle_errors
def export(article_id: str, target: Path) -> None:
    """Exporte les images et l'annonce d'un article dans un dossier."""
    article = storage.load(article_id)
    if article.listing is None:
        raise errors.VtoError("Cet article n'a pas encore d'annonce : lance d'abord « vto run ».")
    export_article(article, target)
    typer.echo(f"Exporté dans {target}")
