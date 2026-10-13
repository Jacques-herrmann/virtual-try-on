"""Chargement de `vinted.json` : version distante, sinon cache, sinon copie embarquée."""

import logging
import os
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Literal

import httpx
from pydantic import ValidationError

from vto.core import paths
from vto.licensing.client import bearer, license_url, same_origin
from vto.vinted.schema import FORMAT, VintedData

log = logging.getLogger(__name__)

TIMEOUT = 5.0

Source = Literal["remote", "cache", "bundled"]


class _NoToken(Exception):
    pass


@dataclass(frozen=True)
class LoadedData:
    data: VintedData
    source: Source
    revision: str


def default_url() -> str:
    """Relayé par le Worker de licence ; le numéro de format fait partie du chemin."""
    return f"{license_url()}/data/vinted-v{FORMAT}.json"


def bundled_text() -> str:
    return files("vto.vinted.data").joinpath("vinted.json").read_text(encoding="utf-8")


def _cache_files() -> tuple[Path, Path]:
    cache = paths.cache_dir()
    return cache / f"vinted-v{FORMAT}.json", cache / f"vinted-v{FORMAT}.etag"


def _read_cache() -> VintedData | None:
    data_file, _ = _cache_files()
    if not data_file.is_file():
        return None
    try:
        return VintedData.model_validate_json(data_file.read_bytes())
    except (ValidationError, ValueError) as exc:
        log.warning("Le cache de vinted.json est inutilisable : %s", _short(exc))
        return None


def _write_atomic(target: Path, content: bytes) -> None:
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_bytes(content)
    try:
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _write_cache(content: bytes, etag: str | None) -> None:
    data_file, etag_file = _cache_files()
    try:
        _write_atomic(data_file, content)
        if etag:
            _write_atomic(etag_file, etag.encode())
        else:
            etag_file.unlink(missing_ok=True)
    except OSError as exc:
        log.warning("Impossible d'écrire le cache vinted.json : %s", exc)


def _short(exc: Exception) -> str:
    return str(exc).splitlines()[0][:200]


def _fetch(
    url: str, etag: str | None, transport: httpx.BaseTransport | None, token: str | None
) -> httpx.Response:
    headers = bearer(url, token)
    if etag:
        headers["If-None-Match"] = etag
    with httpx.Client(transport=transport, timeout=TIMEOUT, follow_redirects=True) as client:
        return client.get(url, headers=headers)


def load_vinted_data(
    transport: httpx.BaseTransport | None = None, token: str | None = None
) -> LoadedData:
    """Ne lève jamais : la copie embarquée est livrée avec l'app et testée.

    Le Worker ne sert le fichier qu'aux abonnés : sans jeton, aucune requête.
    """
    url = os.environ.get("VTO_VINTED_DATA_URL") or default_url()
    cached = _read_cache()
    _, etag_file = _cache_files()
    etag = etag_file.read_text(encoding="utf-8").strip() if cached and etag_file.is_file() else None

    reason = None
    try:
        if token is None and same_origin(url, license_url()):
            raise _NoToken()
        response = _fetch(url, etag, transport, token)
        if response.status_code == 304 and cached is not None:
            return _loaded(cached, "cache", "inchangée depuis le dernier téléchargement")
        if response.status_code == 200:
            data = VintedData.model_validate_json(response.content)
            _write_cache(response.content, response.headers.get("ETag"))
            return _loaded(data, "remote")
        reason = f"HTTP {response.status_code}"
    except _NoToken:
        reason = "pas d'abonnement actif, fichier distant non demandé"
    except httpx.HTTPError as exc:
        reason = f"réseau : {type(exc).__name__} {_short(exc)}"
    except (ValidationError, ValueError) as exc:
        reason = f"fichier distant invalide : {_short(exc)}"

    if cached is not None:
        return _loaded(cached, "cache", f"repli ({reason})")
    data = VintedData.model_validate_json(bundled_text())
    return _loaded(data, "bundled", f"repli ({reason})")


def _loaded(data: VintedData, source: Source, note: str | None = None) -> LoadedData:
    level = logging.WARNING if note and note.startswith("repli") else logging.INFO
    log.log(
        level,
        "Données Vinted : source %s, révision %s%s",
        source, data.revision, f", {note}" if note else "",
    )
    return LoadedData(data=data, source=source, revision=data.revision)
