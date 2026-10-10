import os

from fastapi import APIRouter, Response

from vto.core import paths
from vto.core.errors import VtoError

router = APIRouter(prefix="/api/system")


@router.post("/open-logs", status_code=204)
def open_logs() -> Response:
    """Ouvre le dossier des logs dans l'explorateur (aide au support)."""
    startfile = getattr(os, "startfile", None)
    if startfile is None:
        raise VtoError("Disponible uniquement sous Windows.")
    startfile(paths.logs_dir())
    return Response(status_code=204)
