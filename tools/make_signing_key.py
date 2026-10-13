"""Génère une paire de clés Ed25519 pour signer les jetons de licence.

    python tools/make_signing_key.py k2

- clé privée (PKCS8, base64) : `wrangler secret put TOKEN_PRIVATE_KEY`, et l'identifiant dans la
  variable `TOKEN_KEY_ID` de `worker/wrangler.toml` ;
- clé publique (brute, base64) : à ajouter à `PUBLIC_KEYS` dans `vto/licensing/token.py`.

Ne jamais commiter la clé privée.
"""

import base64
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main() -> None:
    kid = sys.argv[1] if len(sys.argv) > 1 else "k1"
    private = Ed25519PrivateKey.generate()
    pkcs8 = private.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    raw_public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    print(f"kid : {kid}")
    print(f"TOKEN_PRIVATE_KEY (secret) : {base64.b64encode(pkcs8).decode()}")
    print(f'PUBLIC_KEYS["{kid}"] = "{base64.b64encode(raw_public).decode()}"')


if __name__ == "__main__":
    main()
