"""Appels au Worker de licence : activation, rafraîchissement du jeton, désactivation, portail."""

import logging
import os
from urllib.parse import urlsplit

import httpx

from vto.licensing import LicenseError

log = logging.getLogger(__name__)

# Worker de licence (Cloudflare) ; surchargeable par VTO_LICENSE_URL (développement, essais).
DEFAULT_URL = "https://vto-licence.vto-licence.workers.dev"
TIMEOUT = 10.0
MAX_DEVICES = 2

_MESSAGES = {
    "unknown_key": (
        "Cette clé de licence n'existe pas. Vérifie-la dans l'e-mail reçu après l'achat."
    ),
    "expired": (
        "Ton abonnement est terminé. "
        "Renouvelle-le pour continuer à générer et à envoyer sur Vinted."
    ),
    "not_activated": "Ce PC n'est pas activé avec cette clé.",
}


class LicenseUnreachable(LicenseError):
    """Worker injoignable ou réponse inattendue : détails dans le log."""

    user_message = "Impossible de vérifier ton abonnement. Vérifie ta connexion Internet."


class LicenseRefused(LicenseError):
    """Refus explicite du Worker, identifié par `code`."""

    def __init__(self, code: str, devices: list[str] | None = None):
        self.code = code
        self.devices = devices or []
        if code == "too_many_devices":
            message = (
                f"Ta clé est déjà utilisée sur {MAX_DEVICES} PC ({', '.join(self.devices)}). "
                "Désactive-la sur l'un d'eux, ou attends 30 jours sans utilisation."
            )
        else:
            message = _MESSAGES[code]
        super().__init__(message)


def license_url() -> str:
    return (os.environ.get("VTO_LICENSE_URL") or DEFAULT_URL).rstrip("/")


def same_origin(a: str, b: str) -> bool:
    pa, pb = urlsplit(a), urlsplit(b)
    return (pa.scheme, pa.netloc.lower()) == (pb.scheme, pb.netloc.lower())


def bearer(url: str, token: str | None) -> dict[str, str]:
    """En-tête d'autorisation, envoyé seulement au Worker de licence."""
    if token and same_origin(url, license_url()):
        return {"Authorization": f"Bearer {token}"}
    return {}


def _allowed_url(url: str) -> bool:
    parts = urlsplit(url)
    # http seulement en local, pour `wrangler dev`.
    return parts.scheme == "https" or (parts.scheme == "http" and parts.hostname == "127.0.0.1")


class LicenseClient:
    def __init__(self, base_url: str | None = None, transport: httpx.BaseTransport | None = None):
        self.base_url = (base_url or license_url()).rstrip("/")
        self._transport = transport

    def activate(self, key: str, device_id: str, device_name: str) -> str:
        return self._token(
            "/api/activate", {"key": key, "device_id": device_id, "device_name": device_name}
        )

    def refresh(self, key: str, device_id: str) -> str:
        return self._token("/api/token", {"key": key, "device_id": device_id})

    def deactivate(self, key: str, device_id: str) -> None:
        self._request("POST", "/api/deactivate", json={"key": key, "device_id": device_id})

    def portal_url(self, token: str) -> str:
        """Adresse d'une session du portail client Stripe (le Worker y redirige)."""
        response = self._send(
            "GET", "/api/portal", headers={"Authorization": f"Bearer {token}"}
        )
        location = response.headers.get("Location")
        if response.status_code in (302, 303) and location and location.startswith("https://"):
            return location
        log.warning("Portail Stripe : réponse inattendue du Worker (HTTP %s)", response.status_code)
        raise LicenseUnreachable()

    def _token(self, path: str, body: dict) -> str:
        data = self._request("POST", path, json=body)
        token = data.get("token") if isinstance(data, dict) else None
        if not isinstance(token, str):
            log.warning("Worker de licence : réponse sans jeton sur %s", path)
            raise LicenseUnreachable()
        return token

    def _request(self, method: str, path: str, **kwargs) -> dict:
        response = self._send(method, path, **kwargs)
        try:
            data = response.json()
        except ValueError:
            data = None
        if response.status_code == 200 and isinstance(data, dict):
            return data
        code = data.get("code") if isinstance(data, dict) else None
        if 400 <= response.status_code < 500 and (code in _MESSAGES or code == "too_many_devices"):
            devices = data.get("devices") if isinstance(data.get("devices"), list) else None
            raise LicenseRefused(code, [str(d) for d in devices or []])
        log.warning(
            "Worker de licence : HTTP %s sur %s (code %s)", response.status_code, path, code
        )
        raise LicenseUnreachable()

    def _send(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = self.base_url + path
        if not _allowed_url(url):
            log.warning("URL du Worker de licence refusée : %s", url)
            raise LicenseUnreachable()
        try:
            with httpx.Client(transport=self._transport, timeout=TIMEOUT) as client:
                return client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            log.warning("Worker de licence injoignable (%s) : %s", path, type(exc).__name__)
            raise LicenseUnreachable() from exc
