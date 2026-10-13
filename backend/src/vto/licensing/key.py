"""Clé de licence `VTO-XXXX-XXXX-XXXX-XXXX` (alphabet de Crockford, comme le Worker)."""

import hashlib
import re

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_SEPARATORS = re.compile(r"[\s\-_]")


def normalize_key(text: str) -> str | None:
    """Forme canonique d'une clé saisie à la main, ou None si elle est mal formée.

    Tolère minuscules, espaces, tirets manquants, et la confusion 0/O, 1/I/L.
    """
    raw = _SEPARATORS.sub("", text.upper())
    if len(raw) == 19 and raw.startswith(("VTO", "VT0")):
        raw = raw[3:]
    if len(raw) != 16:
        return None
    raw = raw.replace("O", "0").replace("I", "1").replace("L", "1")
    if any(c not in ALPHABET for c in raw):
        return None
    return "VTO-" + "-".join(raw[i : i + 4] for i in range(0, 16, 4))


def key_hint(key: str) -> str:
    """Indice affichable : jamais la clé entière."""
    return f"VTO-…-{key[-4:]}"


def license_hash(key: str) -> str:
    """Empreinte de la clé portée par les jetons (champ `lic`)."""
    return hashlib.sha256(key.encode()).hexdigest()[:16]
