"""État de la licence de ce PC : clé, jeton, rafraîchissement périodique."""

import json
import logging
import os
import platform
import threading
import time
import uuid
from collections.abc import Callable
from typing import Literal, Protocol
from urllib.parse import urlencode

from vto.core import paths
from vto.licensing import LicenseError
from vto.licensing.client import (
    MAX_DEVICES,
    LicenseClient,
    LicenseRefused,
    LicenseUnreachable,
    license_url,
)
from vto.licensing.key import key_hint, license_hash, normalize_key
from vto.licensing.token import InvalidToken, TokenClaims, verify_token

log = logging.getLogger(__name__)

INTERVAL = 24 * 3600.0
BAD_FORMAT = "Cette clé n'a pas le bon format. Elle ressemble à VTO-XXXX-XXXX-XXXX-XXXX."
NO_KEY = "Aucune licence sur ce PC."

State = Literal["none", "active", "expired", "unverified"]


class Client(Protocol):
    def activate(self, key: str, device_id: str, device_name: str) -> str: ...
    def refresh(self, key: str, device_id: str) -> str: ...
    def deactivate(self, key: str, device_id: str) -> None: ...
    def portal_url(self, token: str) -> str: ...


def _device_name() -> str:
    return (platform.node() or "PC")[:100]


class LicenseManager:
    """Clé et jeton de ce PC (`license.json`), rafraîchis au démarrage puis toutes les 24 h.

    Le jeton, vérifié hors ligne, suffit tant qu'il est valide : une panne du Worker ne bloque
    personne avant son expiration (7 jours au plus).
    """

    def __init__(
        self,
        client: Client | None = None,
        public_keys: dict[str, str] | None = None,
        interval: float = INTERVAL,
        now: Callable[[], float] = time.time,
        frozen: Callable[[], bool] = paths.is_frozen,
        device_name: Callable[[], str] = _device_name,
    ):
        self._client = client or LicenseClient()
        self._public_keys = public_keys
        self._interval = interval
        self._now = now
        self._frozen = frozen
        self._device_name = device_name
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # Le Worker a répondu « abonnement terminé » (non persisté : revérifié au démarrage).
        self._ended = False
        # Dernier refus du Worker à montrer au vendeur (2 PC déjà actifs…).
        self._problem: str | None = None
        self._data = self._load()
        if not self._data.get("device_id"):
            self._data["device_id"] = str(uuid.uuid4())
            self._save()

    # --- persistance ---

    def _load(self) -> dict:
        file = paths.license_file()
        if not file.is_file():
            return {}
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            log.warning("license.json illisible, licence à ressaisir")
            return {}
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items() if k in ("key", "device_id", "token") and v}

    def _save(self) -> None:
        file = paths.license_file()
        tmp = file.with_name(file.name + ".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        try:
            os.replace(tmp, file)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    # --- lecture ---

    @property
    def device_id(self) -> str:
        return self._data["device_id"]

    def _dev_bypass(self) -> bool:
        return os.environ.get("VTO_DEV_LICENSE") == "1" and not self._frozen()

    def _claims(self) -> TokenClaims | None:
        """Contenu du jeton s'il est bien signé et émis pour cette clé et ce PC."""
        key, token = self._data.get("key"), self._data.get("token")
        if not key or not token:
            return None
        try:
            claims = verify_token(token, public_keys=self._public_keys)
        except InvalidToken:
            return None
        if claims.lic != license_hash(key) or claims.dev != self.device_id:
            return None
        return claims

    def state(self) -> State:
        if self._dev_bypass():
            return "active"
        with self._lock:
            if not self._data.get("key"):
                return "none"
            claims = self._claims()
            if claims and not claims.is_expired(self._now()):
                return "expired" if claims.subscription_ended else "active"
            return "expired" if self._ended else "unverified"

    def licensed(self) -> bool:
        return self.state() == "active"

    def token(self) -> str | None:
        """Jeton à présenter au Worker (mises à jour, vinted.json), s'il est utilisable."""
        with self._lock:
            key = self._data.get("key")
            claims = self._claims()
            if key and claims and claims.usable(key=key, device_id=self.device_id, now=self._now()):
                return self._data["token"]
            return None

    def snapshot(self) -> dict:
        with self._lock:
            key = self._data.get("key")
            claims = self._claims()
            problem = self._problem
        return {
            "state": self.state(),
            "key_hint": key_hint(key) if key else None,
            "status": claims.status if claims else None,
            "period_end": claims.period_end if claims else None,
            "devices_max": MAX_DEVICES,
            "message": problem,
        }

    # --- actions ---

    def activate(self, text: str) -> None:
        key = normalize_key(text)
        if key is None:
            raise LicenseError(BAD_FORMAT)
        with self._lock:
            try:
                token = self._client.activate(key, self.device_id, self._device_name())
            except LicenseRefused as exc:
                if exc.code == "expired":
                    self._data["key"] = key
                    self._data.pop("token", None)
                    self._ended = True
                    self._save()
                raise
            self._store(key, token)
        log.info("Licence activée (%s)", key_hint(key))

    def deactivate(self) -> None:
        with self._lock:
            key = self._data.get("key")
            if key:
                try:
                    self._client.deactivate(key, self.device_id)
                except LicenseRefused as exc:
                    if exc.code != "unknown_key":
                        raise
            self._data.pop("key", None)
            self._data.pop("token", None)
            self._ended = False
            self._problem = None
            self._save()
        log.info("Licence désactivée sur ce PC")

    def portal_url(self) -> str:
        token = self.token()
        if token is None:
            raise LicenseError()
        return self._client.portal_url(token)

    def renew_url(self) -> str:
        """Page du Worker qui reprend l'abonnement sur le même client Stripe (même clé)."""
        with self._lock:
            key = self._data.get("key")
        if not key:
            raise LicenseError(NO_KEY)
        return f"{license_url()}/renouveler?{urlencode({'cle': key})}"

    def refresh_now(self) -> None:
        with self._lock:
            key = self._data.get("key")
            if not key:
                return
            token = self._data.get("token")
            try:
                if token and self._claims() is None:
                    # Jeton illisible ou d'une autre clé : nouvelle activation silencieuse.
                    log.warning("Jeton de licence invalide, réactivation")
                    new = self._client.activate(key, self.device_id, self._device_name())
                else:
                    try:
                        new = self._client.refresh(key, self.device_id)
                    except LicenseRefused as exc:
                        if exc.code != "not_activated":
                            raise
                        log.info("PC plus activé côté Worker, réactivation")
                        new = self._client.activate(key, self.device_id, self._device_name())
            except LicenseUnreachable:
                log.warning("Rafraîchissement de la licence impossible, jeton conservé")
                return
            except LicenseRefused as exc:
                log.warning("Licence refusée par le Worker : %s", exc.code)
                if exc.code == "expired":
                    self._ended = True
                    self._data.pop("token", None)
                    self._save()
                else:
                    self._problem = exc.user_message
                return
            self._store(key, new)

    def _store(self, key: str, token: str) -> None:
        self._data["key"] = key
        self._data["token"] = token
        self._ended = False
        self._problem = None
        self._save()

    # --- thread ---

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="license-refresh", daemon=True)
        self._thread.start()

    def stop(self, timeout: float | None = 5) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)

    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.refresh_now()
            except Exception:
                log.exception("Erreur inattendue pendant le rafraîchissement de la licence")
            self._stop.wait(self._interval)
