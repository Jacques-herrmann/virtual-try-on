"""File de génération : un thread traite les articles un par un, dans l'ordre d'arrivée."""

import logging
import threading
from collections import deque
from collections.abc import Callable, Sequence

from vto.core import config, errors, pipeline, storage
from vto.core.models import Article

log = logging.getLogger(__name__)


class GenerationQueue:
    def __init__(
        self,
        client_factory: pipeline.ClientFactory | None = None,
        *,
        process: Callable[..., object] = pipeline.process_article,
    ):
        self._client_factory = client_factory
        self._process = process
        # Choix Vinted pour l'annonce ; posé par `create_app` (None = annonce libre).
        self.choices_for: pipeline.ChoicesProvider | None = None
        self._pending: deque[str] = deque()
        self._cond = threading.Condition()
        self._current: str | None = None
        self._cancel: threading.Event | None = None
        self._paused = False
        self._reason: str | None = None
        self._stopped = False
        self._thread: threading.Thread | None = None

    # --- Commandes ------------------------------------------------------------------------

    def start(self) -> None:
        """Reprend les articles laissés en file (ou interrompus) puis lance le thread."""
        with self._cond:
            for article in storage.recover_interrupted():
                if article.id not in self._pending:
                    self._pending.append(article.id)
        self._thread = threading.Thread(target=self._run, name="generation-queue", daemon=True)
        self._thread.start()

    def enqueue(
        self,
        article_id: str,
        *,
        scene_slugs: Sequence[str] | None = None,
        regenerate_listing: bool = False,
    ) -> Article:
        """Met l'article en file et renvoie son état juste après (statut `QUEUED`)."""
        with self._cond:
            article = storage.load(article_id)
            storage.enqueue(
                article, scene_slugs=scene_slugs, regenerate_listing=regenerate_listing
            )
            self._pending.append(article_id)
            self._cond.notify_all()
            return article.model_copy(deep=True)

    def cancel(self, article_id: str) -> None:
        with self._cond:
            if article_id in self._pending:
                self._pending.remove(article_id)
                storage.cancel_queued(storage.load(article_id))
                self._cond.notify_all()
            elif article_id == self._current and self._cancel is not None:
                self._cancel.set()
            else:
                raise errors.VtoError("Cet article n'est pas en cours de génération.")

    def resume(self) -> None:
        with self._cond:
            self._paused = False
            self._reason = None
            self._cond.notify_all()

    def stop(self) -> None:
        """N'accepte plus de travail ; l'article en cours sera repris au prochain lancement."""
        with self._cond:
            self._stopped = True
            self._cond.notify_all()

    # --- État -----------------------------------------------------------------------------

    def status(self) -> dict:
        with self._cond:
            return {
                "running": self._current,
                "pending": list(self._pending),
                "paused": self._paused,
                "reason": self._reason,
            }

    def _idle(self) -> bool:
        return self._current is None and (not self._pending or self._paused or self._stopped)

    def wait_idle(self, timeout: float | None = None) -> bool:
        """Attend que plus rien ne soit traitable (utile aux tests et à l'arrêt)."""
        with self._cond:
            return self._cond.wait_for(self._idle, timeout)

    # --- Thread ---------------------------------------------------------------------------

    def _pause(self, exc: errors.VtoError) -> None:
        self._paused = True
        self._reason = exc.user_message

    def _next(self) -> tuple[str, threading.Event] | None:
        with self._cond:
            self._cond.wait_for(
                lambda: self._stopped or (self._pending and not self._paused)
            )
            if self._stopped:
                return None
            self._current = self._pending.popleft()
            self._cancel = threading.Event()
            return self._current, self._cancel

    def _run(self) -> None:
        while (item := self._next()) is not None:
            article_id, cancel = item
            try:
                settings = config.load_settings()
                try:
                    client = pipeline.build_client(settings, self._client_factory)
                except errors.MissingApiKey as exc:
                    # Rien n'a démarré : l'article reprend sa place en tête de file.
                    with self._cond:
                        self._pending.appendleft(article_id)
                        self._pause(exc)
                    continue
                extra = {"choices_for": self.choices_for} if self.choices_for else {}
                self._process(
                    article_id, client=client, settings=settings, cancel=cancel, **extra
                )
            except pipeline.FATAL as exc:
                log.warning("File en pause : %s", type(exc).__name__)
                with self._cond:
                    self._pause(exc)
            except Exception:
                log.exception("Échec du traitement de l'article %s", article_id)
            finally:
                with self._cond:
                    self._current = None
                    self._cancel = None
                    self._cond.notify_all()
