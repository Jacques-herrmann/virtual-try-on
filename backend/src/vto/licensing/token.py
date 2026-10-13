"""Vérification hors ligne des jetons Ed25519 émis par le Worker de licence.

Jeton : `base64url(payload JSON).base64url(signature de la première partie)`.
"""

import base64
import binascii
import json
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from vto.licensing.key import license_hash

# Clés publiques par identifiant (`kid`) : en ajouter une permet de changer la clé de signature
# du Worker sans casser les versions installées (tools/make_signing_key.py).
PUBLIC_KEYS: dict[str, str] = {
    "k1": "NizMu9SzxUODK1Hkfe4LnW8N07CPJdv/klMQoK/84p8=",
}

RUNNING_STATUSES = frozenset({"trialing", "active", "past_due"})


class InvalidToken(Exception):
    """Jeton illisible, mal signé ou signé par une clé inconnue."""


@dataclass(frozen=True)
class TokenClaims:
    kid: str
    lic: str
    dev: str
    status: str
    period_end: int | None
    exp: int
    iat: int

    @property
    def subscription_ended(self) -> bool:
        return self.status not in RUNNING_STATUSES

    def is_expired(self, now: float) -> bool:
        return self.exp <= now

    def usable(self, *, key: str, device_id: str, now: float) -> bool:
        """Jeton de cette clé, de ce PC, non expiré, abonnement en cours."""
        return (
            self.lic == license_hash(key)
            and self.dev == device_id
            and not self.is_expired(now)
            and not self.subscription_ended
        )


def _b64url(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def verify_token(token: str, public_keys: dict[str, str] | None = None) -> TokenClaims:
    """Vérifie la signature et rend le contenu ; lève InvalidToken sinon."""
    keys = PUBLIC_KEYS if public_keys is None else public_keys
    try:
        payload, sig = token.split(".")
        data = json.loads(_b64url(payload))
        raw_key = keys.get(data["kid"]) if isinstance(data, dict) else None
        if raw_key is None:
            raise InvalidToken("clé de signature inconnue")
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(raw_key))
        public.verify(_b64url(sig), payload.encode())
        if data.get("v") != 1:
            raise InvalidToken("version de jeton inconnue")
        return TokenClaims(
            kid=str(data["kid"]),
            lic=str(data["lic"]),
            dev=str(data["dev"]),
            status=str(data["status"]),
            period_end=None if data["period_end"] is None else int(data["period_end"]),
            exp=int(data["exp"]),
            iat=int(data["iat"]),
        )
    except InvalidToken:
        raise
    except (ValueError, KeyError, TypeError, binascii.Error, InvalidSignature) as exc:
        raise InvalidToken(type(exc).__name__) from exc
