"""Jetons de test signés avec la clé du vecteur partagé (kid `test`)."""

import base64
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from vto.licensing.key import license_hash

PRIVATE = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
PUBLIC_KEYS = {"test": "ebVWLo/mVPlAeLES6KmLp5AfhTrmlb7X4OORC60ElmQ="}
NOW = 1_800_000_000
KEY = "VTO-ABCD-EFGH-JKMN-PQRS"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_token(
    device_id: str,
    *,
    key: str = KEY,
    status: str = "active",
    iat: int = NOW,
    exp: int | None = None,
    period_end: int | None = NOW + 30 * 86400,
    kid: str = "test",
    private: Ed25519PrivateKey = PRIVATE,
) -> str:
    claims = {
        "v": 1,
        "kid": kid,
        "lic": license_hash(key),
        "dev": device_id,
        "status": status,
        "period_end": period_end,
        "exp": exp if exp is not None else iat + 7 * 86400,
        "iat": iat,
    }
    payload = _b64url(json.dumps(claims, separators=(",", ":")).encode())
    return f"{payload}.{_b64url(private.sign(payload.encode()))}"
