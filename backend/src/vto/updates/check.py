"""Vérification périodique du manifeste : à jour, mise à jour disponible ou obligatoire."""

import logging
import threading
from collections.abc import Callable
from typing import Literal

from packaging.version import Version

from vto import __version__
from vto.core import paths
from vto.updates.manifest import Manifest, ManifestUnavailable, fetch_manifest

log = logging.getLogger(__name__)

INTERVAL = 6 * 3600.0

Status = Literal["unknown", "up_to_date", "available", "required"]


def compute_status(current: str, manifest: Manifest) -> Status:
    installed = Version(current)
    if installed < Version(manifest.minimum_version):
        return "required"
    if installed < Version(manifest.version):
        return "available"
    return "up_to_date"


class UpdateChecker:
    """Thread démon : vérifie au démarrage puis toutes les `interval` secondes.

    Un échec garde le dernier état valide : une coupure réseau ne lève pas un blocage.
    """

    def __init__(
        self,
        current: str = __version__,
        fetch: Callable[[], Manifest] = fetch_manifest,
        interval: float = INTERVAL,
        frozen: Callable[[], bool] | None = None,
        enabled: Callable[[], bool] = lambda: True,
    ):
        self.current = current
        # Sans abonnement actif, le Worker refuserait : on ne vérifie pas (état « inconnu »).
        self._enabled = enabled
        self._fetch = fetch
        self._interval = interval
        self._frozen = frozen or paths.is_frozen
        self._lock = threading.Lock()
        self._manifest: Manifest | None = None
        self._status: Status = "unknown"
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="update-check", daemon=True)
        self._thread.start()

    def stop(self, timeout: float | None = 5) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)

    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run(self) -> None:
        while not self._stop.is_set():
            self.check_now()
            self._stop.wait(self._interval)

    def check_now(self) -> None:
        if not self._enabled():
            log.info("Vérification des mises à jour sautée : pas d'abonnement actif")
            return
        try:
            manifest = self._fetch()
        except ManifestUnavailable as exc:
            log.warning("Vérification des mises à jour impossible : %s", exc)
            return
        except Exception:
            log.exception("Erreur inattendue pendant la vérification des mises à jour")
            return
        status = compute_status(self.current, manifest)
        with self._lock:
            self._manifest, self._status = manifest, status
        log.info(
            "Mises à jour : installée %s, publiée %s, minimum %s → %s",
            self.current, manifest.version, manifest.minimum_version, status,
        )

    @property
    def manifest(self) -> Manifest | None:
        with self._lock:
            return self._manifest

    def is_required(self) -> bool:
        with self._lock:
            return self._status == "required"

    def snapshot(self) -> dict:
        with self._lock:
            manifest, status = self._manifest, self._status
        return {
            "current": self.current,
            "latest": manifest.version if manifest else None,
            "status": status,
            "notes": manifest.notes if manifest else "",
            "can_install": self._frozen(),
        }
