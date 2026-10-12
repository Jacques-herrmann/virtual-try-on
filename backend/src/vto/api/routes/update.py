from fastapi import APIRouter, HTTPException, Request

from vto.updates import UpdateError

router = APIRouter(prefix="/api/update")

NOT_INSTALLED = "Mise à jour possible uniquement depuis l'application installée."
NOTHING_TO_INSTALL = "Aucune mise à jour à installer."
GENERATING = "Une génération est en cours. La mise à jour sera possible quand elle sera terminée."
VINTED_BUSY = (
    "Une opération Vinted est en cours. La mise à jour sera possible quand elle sera terminée."
)


@router.get("")
def status(request: Request) -> dict:
    return request.app.state.updates.snapshot()


@router.post("/install", status_code=202)
def install(request: Request) -> dict:
    state = request.app.state
    snapshot = state.updates.snapshot()
    manifest = state.updates.manifest
    if not snapshot["can_install"]:
        raise HTTPException(409, NOT_INSTALLED)
    if manifest is None or snapshot["status"] not in ("available", "required"):
        raise HTTPException(409, NOTHING_TO_INSTALL)
    # L'installeur ferme l'app : on ne coupe jamais un travail en cours.
    if state.queue.is_busy():
        raise HTTPException(409, GENERATING)
    if state.vinted.is_busy():
        raise HTTPException(409, VINTED_BUSY)
    try:
        state.installer.start(manifest)
    except UpdateError as exc:
        raise HTTPException(409, exc.user_message) from exc
    return state.installer.progress()


@router.get("/progress")
def progress(request: Request) -> dict:
    return request.app.state.installer.progress()
