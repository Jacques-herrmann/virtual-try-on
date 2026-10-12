"""Téléchargement de l'installeur, vérification SHA-256, lancement silencieux puis arrêt."""

import hashlib
import logging
import os
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import httpx

from vto.core import paths
from vto.updates import UpdateError
from vto.updates.manifest import Manifest

log = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(60.0, connect=10.0)
CHUNK = 256 * 1024

State = Literal["idle", "downloading", "launching", "error"]

DOWNLOAD_FAILED = "Le téléchargement de la mise à jour a échoué. Vérifie ta connexion et réessaie."
CORRUPTED = "La mise à jour téléchargée est abîmée. Réessaie dans quelques minutes."
BLOCKED = "Windows a bloqué la mise à jour. Consulte la page d'aide pour l'autoriser."
ALREADY_RUNNING = "La mise à jour est déjà en cours."


def installer_args(path: Path, version: str) -> list[str]:
    return [
        str(path),
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        f"/LOG={paths.logs_dir() / f'update-{version}.log'}",
    ]


def launch_detached(args: list[str]) -> None:
    # L'installeur doit survivre à la fermeture de l'app, qu'il attend pour remplacer ses fichiers.
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
    )
    subprocess.Popen(args, creationflags=flags, close_fds=True)


def clean_old_installers() -> None:
    """Supprime les installeurs déjà utilisés ou abandonnés (fichiers de l'app, pas du client)."""
    for path in paths.updates_cache_dir().iterdir():
        if path.is_file() and path.name.endswith((".exe", ".exe.part")):
            try:
                path.unlink()
            except OSError as exc:
                log.warning("Impossible de supprimer %s : %s", path.name, exc)


class Installer:
    def __init__(
        self,
        launcher: Callable[[list[str]], None] = launch_detached,
        on_launched: Callable[[], None] = lambda: None,
        transport: httpx.BaseTransport | None = None,
    ):
        self._launcher = launcher
        self._on_launched = on_launched
        self._transport = transport
        self._lock = threading.Lock()
        self._state: State = "idle"
        self._received = 0
        self._total: int | None = None
        self._message: str | None = None

    def progress(self) -> dict:
        with self._lock:
            return {
                "state": self._state,
                "received": self._received,
                "total": self._total,
                "message": self._message,
            }

    def _set(self, **changes) -> None:
        with self._lock:
            for key, value in changes.items():
                setattr(self, f"_{key}", value)

    def _claim(self) -> None:
        with self._lock:
            if self._state in ("downloading", "launching"):
                raise UpdateError(ALREADY_RUNNING)
            self._state, self._received, self._total, self._message = "downloading", 0, None, None

    def start(self, manifest: Manifest) -> None:
        """Lance `run` en arrière-plan ; refuse si une mise à jour est déjà en cours."""
        self._claim()
        threading.Thread(
            target=self._run_claimed, args=(manifest,), name="update-install", daemon=True
        ).start()

    def run(self, manifest: Manifest) -> None:
        self._claim()
        self._run_claimed(manifest)

    def _run_claimed(self, manifest: Manifest) -> None:
        try:
            path = self._download(manifest)
            self._set(state="launching")
            try:
                self._launcher(installer_args(path, manifest.version))
            except OSError as exc:
                log.error("Lancement de l'installeur impossible : %s", exc)
                raise UpdateError(BLOCKED) from exc
            log.info("Installeur %s lancé, fermeture de l'application", manifest.version)
            self._on_launched()
        except UpdateError as exc:
            self._set(state="error", message=exc.user_message)
        except Exception:
            log.exception("Erreur inattendue pendant la mise à jour")
            self._set(state="error", message=UpdateError.user_message)

    def _download(self, manifest: Manifest) -> Path:
        folder = paths.updates_cache_dir()
        target = folder / f"VirtualTryOn-Setup-{manifest.version}.exe"
        part = target.with_name(target.name + ".part")
        digest = hashlib.sha256()
        try:
            with (
                httpx.Client(
                    transport=self._transport, timeout=TIMEOUT, follow_redirects=True
                ) as client,
                client.stream("GET", manifest.url) as response,
            ):
                response.raise_for_status()
                length = response.headers.get("Content-Length")
                self._set(total=int(length) if length and length.isdigit() else None)
                with part.open("wb") as out:
                    for chunk in response.iter_bytes(CHUNK):
                        out.write(chunk)
                        digest.update(chunk)
                        with self._lock:
                            self._received += len(chunk)
        except (httpx.HTTPError, OSError) as exc:
            part.unlink(missing_ok=True)
            log.error("Téléchargement de %s impossible : %s", manifest.url, exc)
            raise UpdateError(DOWNLOAD_FAILED) from exc

        if digest.hexdigest() != manifest.sha256:
            part.unlink(missing_ok=True)
            log.error(
                "Empreinte de l'installeur différente : attendue %s, obtenue %s",
                manifest.sha256, digest.hexdigest(),
            )
            raise UpdateError(CORRUPTED)
        with self._lock:
            self._total = self._received
        os.replace(part, target)
        return target
