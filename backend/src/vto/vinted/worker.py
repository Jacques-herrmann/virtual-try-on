"""Envoi sur Vinted : un thread possède l'unique navigateur et traite les commandes une à une.

L'API synchrone de Playwright n'est utilisée que depuis ce thread.
"""

import logging
import queue
import random
import shutil
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from playwright.sync_api import Error as PlaywrightError

from vto.core import config, errors, paths, storage
from vto.core.models import ArticleStatus, VintedResult
from vto.vinted import browser, filler, remote
from vto.vinted.catalog import Catalog

log = logging.getLogger(__name__)

LOGIN_TIMEOUT = 600.0  # s
LOGIN_POLL = 2.0  # s
PAUSE_RANGE = (4.0, 10.0)  # s, entre deux articles

LOGIN_TIMEOUT_MESSAGE = "Connexion à Vinted non détectée. Réessaie."
DATA_UNAVAILABLE_MESSAGE = "L'envoi sur Vinted est momentanément indisponible."
UNEXPECTED_MESSAGE = "Une erreur inattendue est survenue pendant l'envoi sur Vinted."


class Busy(errors.VtoError):
    user_message = "Un envoi sur Vinted est déjà en cours. Attends qu'il se termine."


class UpdateRequired(errors.VtoError):
    user_message = (
        "Cette version ne fonctionne plus avec Vinted. "
        "Mets l'application à jour pour envoyer tes annonces."
    )


class WindowClosed(Exception):
    """Le vendeur a fermé la fenêtre Vinted."""


def _start_playwright():
    from playwright.sync_api import sync_playwright

    return sync_playwright().start()


def _window_closed(exc: BaseException) -> bool:
    return isinstance(exc, PlaywrightError) and "has been closed" in str(exc)


@dataclass
class Batch:
    running: bool = False
    paused_reason: str | None = None  # "login_required"
    current: str | None = None
    done: int = 0
    total: int = 0
    failed: int = 0
    message: str | None = None  # fin anormale du dernier lot, pour le vendeur
    article_ids: list[str] = field(default_factory=list, repr=False)


class VintedWorker:
    def __init__(
        self,
        *,
        start_playwright: Callable[[], object] = _start_playwright,
        open_context: Callable = browser.open_context,
        is_logged_in: Callable = browser.is_logged_in,
        fill: Callable = filler.fill_item,
        load_data: Callable[[], remote.LoadedData] = remote.load_vinted_data,
        clock: Callable[[], float] = time.monotonic,
        login_timeout: float = LOGIN_TIMEOUT,
        login_poll: float = LOGIN_POLL,
        pause_range: tuple[float, float] = PAUSE_RANGE,
        update_required: Callable[[], bool] = lambda: False,
    ):
        self._start_playwright = start_playwright
        self._open_context = open_context
        self._is_logged_in = is_logged_in
        self._fill = fill
        self._load_data = load_data
        self._clock = clock
        self._login_timeout = login_timeout
        self._login_poll = login_poll
        self._pause_range = pause_range
        self._update_required = update_required

        self._commands: queue.Queue[tuple] = queue.Queue()
        self._lock = threading.Condition()
        self._stop_batch = threading.Event()
        self._busy = False  # commande en cours ou en attente
        self._connected: bool | None = None
        self._connecting = False
        self._loaded: remote.LoadedData | None = None
        self._loaded_event = threading.Event()
        self._batch = Batch()
        self._thread: threading.Thread | None = None
        self._playwright = None
        self._context = None

    # --- Commandes (appelées depuis l'API) ------------------------------------------------

    def start(self) -> None:
        """Lance le thread ; les données Vinted sont chargées en arrière-plan."""
        self._thread = threading.Thread(target=self._run, name="vinted-worker", daemon=True)
        self._thread.start()
        self._commands.put(("load",))

    def shutdown(self, timeout: float | None = 10) -> None:
        """Arrête le lot en cours, ferme le navigateur et le thread (fermeture de l'app)."""
        self._stop_batch.set()
        self._commands.put(("quit",))
        if self._thread is not None:
            self._thread.join(timeout)

    def _submit(self, *command) -> None:
        with self._lock:
            if self._busy:
                raise Busy()
            self._busy = True
            self._commands.put(command)

    def connect(self) -> None:
        with self._lock:
            if self._busy:
                raise Busy()
            self._busy = True
            self._connecting = True
            self._stop_batch.clear()
            self._commands.put(("connect",))

    def disconnect(self) -> None:
        self._submit("disconnect")

    def open_url(self, url: str) -> None:
        self._submit("open", url)

    def send(self, article_ids: Sequence[str]) -> None:
        # Une version trop ancienne remplirait mal le formulaire : on bloque l'envoi seulement.
        if self._update_required():
            log.warning("Envoi Vinted refusé : version trop ancienne, mise à jour obligatoire")
            raise UpdateRequired()
        with self._lock:
            if self._busy:
                raise Busy()
            self._busy = True
            self._stop_batch.clear()
            ids = list(article_ids)
            self._batch = Batch(running=True, total=len(ids), article_ids=ids)
            self._commands.put(("send", ids))

    def stop(self) -> None:
        """Termine l'article en cours, puis arrête le lot."""
        self._stop_batch.set()

    # --- État -----------------------------------------------------------------------------

    @property
    def loaded(self) -> remote.LoadedData | None:
        return self._loaded

    def wait_loaded(self, timeout: float | None = None) -> bool:
        """Attend le premier chargement des données Vinted (lancé par `start`)."""
        return self._loaded_event.wait(timeout)

    def status(self) -> dict:
        with self._lock:
            b = self._batch
            return {
                "connected": self._connected,
                "connecting": self._connecting,
                "data_revision": self._loaded.revision if self._loaded else None,
                "data_source": self._loaded.source if self._loaded else None,
                "batch": {
                    "running": b.running,
                    "paused_reason": b.paused_reason,
                    "current": b.current,
                    "done": b.done,
                    "total": b.total,
                    "failed": b.failed,
                    "message": b.message,
                },
            }

    def is_busy(self) -> bool:
        """Une commande (connexion, envoi…) est en cours ou en attente."""
        with self._lock:
            return self._busy

    def wait_idle(self, timeout: float | None = None) -> bool:
        with self._lock:
            return self._lock.wait_for(lambda: not self._busy, timeout)

    # --- Thread ---------------------------------------------------------------------------

    def _run(self) -> None:
        while True:
            command = self._commands.get()
            name = command[0]
            if name == "quit":
                self._close_context()
                self._stop_playwright()
                return
            try:
                getattr(self, f"_do_{name}")(*command[1:])
            except Exception:
                log.exception("Échec de la commande Vinted %s", name)
            finally:
                with self._lock:
                    if name != "load":
                        self._busy = False
                    self._connecting = False
                    self._batch.running = False
                    self._batch.paused_reason = None
                    self._batch.current = None
                    self._lock.notify_all()

    def _set(self, **changes) -> None:
        with self._lock:
            for key, value in changes.items():
                setattr(self, key, value)

    def _set_batch(self, **changes) -> None:
        with self._lock:
            for key, value in changes.items():
                setattr(self._batch, key, value)

    def _do_load(self) -> remote.LoadedData:
        try:
            loaded = self._load_data()
            self._set(_loaded=loaded)
            return loaded
        finally:
            self._loaded_event.set()

    def _page(self):
        if self._context is None:
            if self._playwright is None:
                self._playwright = self._start_playwright()
            self._context = self._open_context(self._playwright)
        pages = self._context.pages
        return pages[0] if pages else self._context.new_page()

    def _close_context(self) -> None:
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                log.debug("Fermeture du navigateur", exc_info=True)
            self._context = None

    def _stop_playwright(self) -> None:
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                log.debug("Arrêt de Playwright", exc_info=True)
            self._playwright = None

    def _wait_for_login(self, page, data) -> bool:
        """Vérifie la connexion toutes les `login_poll` s jusqu'au délai ou à un arrêt."""
        deadline = self._clock() + self._login_timeout
        while True:
            logged_in = self._is_logged_in(page, data)
            self._set(_connected=logged_in)
            if logged_in:
                return True
            if self._clock() >= deadline or self._stop_batch.wait(self._login_poll):
                return False

    def _do_connect(self) -> None:
        loaded = self._loaded or self._do_load()
        try:
            self._wait_for_login(self._page(), loaded.data)
        except errors.VtoError:
            raise
        except PlaywrightError as exc:
            if not _window_closed(exc):
                raise
            log.info("Fenêtre Vinted fermée pendant la connexion")
        finally:
            self._close_context()

    def _do_disconnect(self) -> None:
        self._close_context()
        # Seul effacement fait par l'envoi Vinted : le profil du navigateur dédié.
        shutil.rmtree(paths.browser_profile_dir(), ignore_errors=True)
        self._set(_connected=False)

    def _do_open(self, url: str) -> None:
        try:
            self._page().goto(url)
        except PlaywrightError as exc:
            if not _window_closed(exc):
                raise
            # Fenêtre fermée depuis : on en rouvre une.
            self._close_context()
            self._page().goto(url)

    def _do_send(self, article_ids: list[str]) -> None:
        try:
            self._send(article_ids)
        except errors.VtoError as exc:
            self._end_batch(exc.user_message)
        except WindowClosed:
            remaining = self._batch.total - self._batch.done
            self._end_batch(
                f"La fenêtre Vinted a été fermée. {remaining} article(s) n'ont pas été envoyés."
            )
        finally:
            self._close_context()
            b = self._batch
            log.info("Lot Vinted terminé : %s/%s, %s échec(s)", b.done, b.total, b.failed)

    def _end_batch(self, message: str) -> None:
        log.warning("Lot Vinted interrompu : %s", message)
        self._set_batch(message=message)

    def _send(self, article_ids: list[str]) -> None:
        try:
            loaded = self._do_load()
        except Exception as exc:
            log.exception("Données Vinted indisponibles")
            raise errors.VtoError(DATA_UNAVAILABLE_MESSAGE) from exc
        catalog = Catalog(loaded.data)
        mode = config.load_settings().vinted_mode

        try:
            page = self._page()
            if not self._is_logged_in(page, loaded.data):
                self._set_batch(paused_reason="login_required")
                if not self._wait_for_login(page, loaded.data):
                    if self._stop_batch.is_set():
                        return
                    raise errors.VtoError(LOGIN_TIMEOUT_MESSAGE)
                self._set_batch(paused_reason=None)
        except PlaywrightError as exc:
            if _window_closed(exc):
                raise WindowClosed() from exc
            raise

        for index, article_id in enumerate(article_ids):
            if index and not self._pause_between_articles():
                return
            self._send_one(page, article_id, loaded.data, catalog, mode)

    def _pause_between_articles(self) -> bool:
        """Pause aléatoire ; False si un arrêt a été demandé pendant la pause."""
        return not self._stop_batch.wait(random.uniform(*self._pause_range))

    def _send_one(self, page, article_id: str, data, catalog, mode) -> None:
        try:
            article = storage.load(article_id)
        except errors.VtoError:
            log.warning("Article %s introuvable, ignoré", article_id)
            self._set_batch(done=self._batch.done + 1)
            return
        if article.status != ArticleStatus.VALIDATED:
            log.info("Article %s ignoré (statut %s)", article_id, article.status.value)
            self._set_batch(done=self._batch.done + 1)
            return

        self._set_batch(current=article_id)
        closed = None
        try:
            report = self._fill(page, article, data, catalog, mode)
        except Exception as exc:
            if _window_closed(exc):
                closed = exc
                log.warning("Fenêtre Vinted fermée pendant l'article %s", article_id)
                message = "La fenêtre Vinted a été fermée pendant l'envoi."
            else:
                log.exception("Échec imprévu de l'envoi de l'article %s", article_id)
                message = UNEXPECTED_MESSAGE
            report = filler.FillReport(mode="draft", status="error", error=message)

        result = VintedResult(
            mode=report.mode,
            status=report.status,
            missing_fields=report.missing_fields,
            url=report.url,
            error=report.error,
            sent_at=datetime.now(UTC),
        )
        storage.record_vinted(article, result)
        log.info(
            "Article %s envoyé sur Vinted : %s (%s)%s", article_id, report.status, report.mode,
            f", à compléter : {', '.join(report.missing_fields)}" if report.missing_fields else "",
        )
        failed = self._batch.failed + (report.status == "error")
        if closed is not None:
            self._set_batch(failed=failed)
            raise WindowClosed() from closed
        self._set_batch(done=self._batch.done + 1, failed=failed)
