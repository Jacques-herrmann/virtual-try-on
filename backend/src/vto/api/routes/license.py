from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from vto.licensing import LicenseError
from vto.licensing.client import MAX_DEVICES, LicenseUnreachable

router = APIRouter(prefix="/api/license")

UNAVAILABLE = "La licence est indisponible dans ce mode."

NO_LICENSE = {
    "state": "none",
    "key_hint": None,
    "status": None,
    "period_end": None,
    "devices_max": MAX_DEVICES,
    "message": None,
}


class KeyRequest(BaseModel):
    key: str


def _manager(request: Request):
    manager = request.app.state.license
    if manager is None:
        raise HTTPException(503, UNAVAILABLE)
    return manager


def _call(action):
    """Erreurs de licence → 400 (refus, à corriger) ou 503 (Worker injoignable, réessayer)."""
    try:
        return action()
    except LicenseUnreachable as exc:
        raise HTTPException(503, exc.user_message) from exc
    except LicenseError as exc:
        raise HTTPException(400, exc.user_message) from exc


@router.get("")
def status(request: Request) -> dict:
    manager = request.app.state.license
    # La clé entière n'est jamais renvoyée : seulement un indice.
    return manager.snapshot() if manager is not None else dict(NO_LICENSE)


@router.post("")
def activate(request: Request, body: KeyRequest) -> dict:
    manager = _manager(request)
    _call(lambda: manager.activate(body.key))
    return manager.snapshot()


@router.delete("")
def deactivate(request: Request) -> dict:
    manager = _manager(request)
    _call(manager.deactivate)
    return manager.snapshot()


@router.get("/portal")
def portal(request: Request) -> dict:
    manager = _manager(request)
    return {"url": _call(manager.portal_url)}
