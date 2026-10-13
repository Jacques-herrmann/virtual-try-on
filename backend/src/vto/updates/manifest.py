"""Manifeste `latest.json` : dernière version publiée et version minimale acceptée."""

import os
import re
from urllib.parse import urlsplit

import httpx
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from vto.licensing.client import bearer, license_url

TIMEOUT = 5.0


class ManifestUnavailable(Exception):
    """Manifeste injoignable ou invalide : on reste silencieux, détails dans le log."""


def _allowed_url(url: str) -> bool:
    parts = urlsplit(url)
    # http seulement en local, pour essayer le bandeau avec un manifeste servi sur le poste.
    return parts.scheme == "https" or (parts.scheme == "http" and parts.hostname == "127.0.0.1")


class Manifest(BaseModel):
    # Champs inconnus ignorés : un manifeste plus récent ne casse pas une ancienne app.
    model_config = ConfigDict(extra="ignore", frozen=True)

    version: str
    minimum_version: str
    url: str
    sha256: str
    notes: str = ""

    @field_validator("version", "minimum_version")
    @classmethod
    def _pep440(cls, value: str) -> str:
        try:
            Version(value)
        except InvalidVersion as exc:
            raise ValueError(f"version invalide : {value!r}") from exc
        return value

    @field_validator("url")
    @classmethod
    def _url(cls, value: str) -> str:
        if not _allowed_url(value):
            raise ValueError(f"URL refusée : {value!r}")
        return value

    @field_validator("sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
            raise ValueError("empreinte SHA-256 invalide")
        return value.lower()

    @model_validator(mode="after")
    def _minimum_not_after_version(self) -> "Manifest":
        if Version(self.minimum_version) > Version(self.version):
            raise ValueError("minimum_version est plus récente que version")
        return self


def default_url() -> str:
    """Manifeste de la dernière Release publiée, relayé par le Worker de licence."""
    return f"{license_url()}/updates/latest.json"


def manifest_url() -> str:
    return os.environ.get("VTO_UPDATE_URL") or default_url()


def fetch_manifest(
    url: str | None = None,
    transport: httpx.BaseTransport | None = None,
    token: str | None = None,
) -> Manifest:
    url = url or manifest_url()
    if not _allowed_url(url):
        raise ManifestUnavailable(f"URL du manifeste refusée : {url}")
    try:
        with httpx.Client(transport=transport, timeout=TIMEOUT, follow_redirects=True) as client:
            response = client.get(url, headers=bearer(url, token))
        response.raise_for_status()
        return Manifest.model_validate_json(response.content)
    except httpx.HTTPError as exc:
        raise ManifestUnavailable(f"{url} : {type(exc).__name__} {exc}") from exc
    except (ValidationError, ValueError) as exc:
        raise ManifestUnavailable(f"{url} : manifeste invalide : {exc}") from exc
