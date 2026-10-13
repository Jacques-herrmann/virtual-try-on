"""Application FastAPI : API locale + front compilé."""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from vto.api import security
from vto.api.queue import GenerationQueue
from vto.api.routes import articles, files, license, scenes, settings, system, update, vinted
from vto.api.routes import queue as queue_routes
from vto.core import errors, paths
from vto.core.pipeline import ClientFactory
from vto.licensing import LicenseError
from vto.licensing.state import LicenseManager
from vto.updates.check import UpdateChecker
from vto.updates.install import Installer
from vto.vinted.worker import Busy, UpdateRequired, VintedWorker

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

MISSING_FRONT = """<!doctype html><meta charset="utf-8"><title>Kaloé</title>
<p>L'interface n'est pas compilée. Lance <code>npm run build</code> dans <code>frontend/</code>.</p>
"""


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"message": message}, status_code=status)


def _add_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(errors.VtoError)
    async def vto_error(request: Request, exc: errors.VtoError):
        status = 400
        if isinstance(exc, errors.ArticleNotFound):
            status = 404
        elif isinstance(exc, errors.InvalidTransition | Busy | UpdateRequired):
            status = 409
        elif isinstance(exc, LicenseError):
            status = 402
        return _error(status, exc.user_message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        log.info("Requête invalide sur %s : %s", request.url.path, exc.errors())
        return _error(422, "Requête invalide.")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        if exc.status_code == 404:
            message = "Introuvable."
        elif (exc.status_code < 500 or exc.status_code == 503) and isinstance(exc.detail, str):
            message = exc.detail
        else:
            message = errors.VtoError.user_message
        return _error(exc.status_code, message)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        log.error("Erreur inattendue sur %s", request.url.path, exc_info=exc)
        return _error(500, errors.VtoError.user_message)


def _add_front(app: FastAPI, static_dir: Path) -> None:
    @app.get("/{path:path}", include_in_schema=False)
    def front(path: str):
        if path.startswith(("api/", "files/")):
            raise HTTPException(404)
        index = static_dir / "index.html"
        if not index.is_file():
            return HTMLResponse(MISSING_FRONT)
        asset = paths.safe_join(static_dir, path) if path else None
        if asset is not None and asset.is_file():
            return FileResponse(asset)
        return FileResponse(index)


def create_app(
    client_factory: ClientFactory | None = None,
    *,
    token: str,
    port: int,
    queue: GenerationQueue | None = None,
    static_dir: Path | None = None,
    vinted_worker: VintedWorker | None = None,
    update_checker: UpdateChecker | None = None,
    installer: Installer | None = None,
    license_manager: LicenseManager | None = None,
) -> FastAPI:
    app = FastAPI(title="Kaloé", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.client_factory = client_factory
    app.state.queue = queue or GenerationQueue(client_factory)
    app.state.vinted = vinted_worker or VintedWorker()
    app.state.queue.choices_for = vinted.choices_provider(app)
    # Sans vérificateur démarré, l'état reste « inconnu » : aucun bandeau.
    app.state.updates = update_checker or UpdateChecker()
    app.state.installer = installer or Installer()
    # Sans gestionnaire (tests, outils), la licence est « absente » et non modifiable.
    app.state.license = license_manager
    app.middleware("http")(security.make_middleware(token, port))
    _add_error_handlers(app)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    routers = (articles, files, license, queue_routes, scenes, settings, system, update, vinted)
    for module in routers:
        app.include_router(module.router)
    _add_front(app, static_dir or STATIC_DIR)
    return app
