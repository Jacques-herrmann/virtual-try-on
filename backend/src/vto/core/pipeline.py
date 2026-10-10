"""Traitement d'un article : images de chaque scène, puis annonce."""

import logging
import threading
from collections.abc import Callable, Sequence

from vto.core import errors, scenes, storage
from vto.core.config import Settings
from vto.core.generation.client import GeminiClient, GenAIClient
from vto.core.generation.image import generate_scene_image
from vto.core.generation.listing import generate_listing
from vto.core.models import Article, ArticleStatus, SceneResult

log = logging.getLogger(__name__)

S = ArticleStatus
ProgressCallback = Callable[[str, str, str], None]
# Construit un client à partir d'une clé ; les tests injectent un FakeClient.
ClientFactory = Callable[[str], GenAIClient]

# Erreurs qui touchent tout le lot : inutile d'enchaîner les échecs.
FATAL = (errors.MissingApiKey, errors.InvalidApiKey, errors.QuotaExceeded)

NO_IMAGE_MESSAGE = "Aucune image n'a pu être générée."


def build_client(settings: Settings, client_factory: ClientFactory | None = None) -> GenAIClient:
    key = settings.api_key()
    if not key:
        raise errors.MissingApiKey()
    return (client_factory or GeminiClient)(key)


def verify_api_key(key: str, settings: Settings, client_factory: ClientFactory) -> None:
    """Vérifie `key` (et non la clé effective des réglages) sur les modèles configurés."""
    key = key.strip()
    if not key:
        raise errors.MissingApiKey()
    client_factory(key).check_models([settings.image_model, settings.text_model])


def _message(exc: Exception) -> str:
    if isinstance(exc, errors.VtoError):
        return exc.user_message
    log.exception("Erreur inattendue")
    return errors.VtoError.user_message


def _fail(article: Article, exc: errors.VtoError) -> None:
    article.error = exc.user_message
    storage.set_status(article, S.ERROR)


def _replace_result(article: Article, result: SceneResult) -> None:
    for i, existing in enumerate(article.scenes):
        if existing.scene == result.scene:
            article.scenes[i] = result
            return
    article.scenes.append(result)


def _finish_cancelled(article: Article) -> Article:
    storage.set_status(article, S.TO_REVIEW if storage.has_output(article) else S.DRAFT)
    return article


def process_article(
    article_id: str,
    *,
    client: GenAIClient,
    settings: Settings,
    scene_slugs: Sequence[str] | None = None,
    regenerate_listing: bool = False,
    cancel: threading.Event | None = None,
    on_progress: ProgressCallback | None = None,
) -> Article:
    """Génère les images (toutes les scènes actives, ou seulement `scene_slugs`) puis l'annonce.

    Pour un article en file (`QUEUED`), la demande enregistrée dans `article.job` remplace
    `scene_slugs` et `regenerate_listing` ; elle est effacée une fois le traitement terminé.

    Une scène en échec n'arrête pas les autres. Les erreurs de `FATAL` passent l'article
    en erreur et sont propagées pour arrêter le lot.
    """
    article = storage.load(article_id)
    try:
        return _process(
            article,
            client=client,
            settings=settings,
            scene_slugs=scene_slugs,
            regenerate_listing=regenerate_listing,
            cancel=cancel or threading.Event(),
            progress=on_progress or (lambda *_: None),
        )
    finally:
        if article.job is not None and article.status != S.QUEUED:
            article.job = None
            storage.save(article)


def _process(
    article: Article,
    *,
    client: GenAIClient,
    settings: Settings,
    scene_slugs: Sequence[str] | None,
    regenerate_listing: bool,
    cancel: threading.Event,
    progress: ProgressCallback,
) -> Article:
    available = {s.slug: s for s in scenes.list_scenes()}
    if article.status == S.QUEUED and article.job is not None:
        scene_slugs = article.job.scene_slugs
        regenerate_listing = article.job.regenerate_listing
        if scene_slugs is not None:
            # Une scène supprimée ou désactivée depuis la mise en file est simplement ignorée.
            dropped = [s for s in scene_slugs if s not in available]
            if dropped:
                log.warning("Scènes ignorées (plus disponibles) : %s", ", ".join(dropped))
            scene_slugs = [s for s in scene_slugs if s in available]

    full_run = scene_slugs is None
    unknown = set(scene_slugs or ()) - available.keys()
    if unknown:
        raise errors.VtoError(f"Scène inconnue ou désactivée : {', '.join(sorted(unknown))}.")
    targets = list(available.values()) if full_run else [available[s] for s in scene_slugs]

    if full_run:
        article.scenes = [SceneResult(scene=s.slug) for s in targets]
        article.listing = None
    else:
        for scene in targets:
            _replace_result(article, SceneResult(scene=scene.slug))
    article.error = None
    storage.set_status(article, S.GENERATING)

    for scene in targets:
        if cancel.is_set():
            return _finish_cancelled(article)
        try:
            image = generate_scene_image(client, settings, scene, article)
            result = SceneResult(scene=scene.slug, status="ok", image=image)
        except FATAL as exc:
            _fail(article, exc)
            raise
        except Exception as exc:
            result = SceneResult(scene=scene.slug, status="error", error=_message(exc))
        _replace_result(article, result)
        storage.save(article)
        progress(article.id, "scene", scene.slug)

    listing_error = None
    if article.listing is None or regenerate_listing:
        if cancel.is_set():
            return _finish_cancelled(article)
        try:
            article.listing = generate_listing(client, settings, article)
        except FATAL as exc:
            _fail(article, exc)
            raise
        except Exception as exc:
            listing_error = _message(exc)
        storage.save(article)
        progress(article.id, "listing", "")

    if not any(s.status == "ok" for s in article.scenes):
        article.error = NO_IMAGE_MESSAGE
        storage.set_status(article, S.ERROR)
    elif article.listing is None:
        article.error = listing_error
        storage.set_status(article, S.ERROR)
    else:
        storage.set_status(article, S.TO_REVIEW)
    progress(article.id, "done", article.status.value)
    return article


def regenerate_listing(article_id: str, **kwargs) -> Article:
    return process_article(article_id, scene_slugs=[], regenerate_listing=True, **kwargs)


def process_batch(article_ids: Sequence[str], **kwargs) -> list[Article]:
    """Traite les articles un par un ; s'arrête sur annulation ou sur une erreur de `FATAL`."""
    cancel: threading.Event | None = kwargs.get("cancel")
    done = []
    for article_id in article_ids:
        if cancel is not None and cancel.is_set():
            break
        done.append(process_article(article_id, **kwargs))
    return done
