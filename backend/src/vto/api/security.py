"""Protection de l'API locale : jeton de session (cookie) et contrôle de l'en-tête Host.

Sans cela, n'importe quel site ouvert dans le navigateur du client pourrait appeler
http://127.0.0.1:<port> et consommer sa clé Gemini.
"""

import secrets

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

COOKIE = "vto_session"
PUBLIC_API = {"/api/health"}


def _protected(path: str) -> bool:
    return (path.startswith("/api/") and path not in PUBLIC_API) or path.startswith("/files/")


def make_middleware(token: str, port: int):
    allowed_host = f"127.0.0.1:{port}"

    async def middleware(request: Request, call_next) -> Response:
        if request.headers.get("host") != allowed_host:
            return JSONResponse({"message": "Requête refusée."}, status_code=400)

        given = request.query_params.get("token")
        if request.url.path == "/" and given is not None:
            if not secrets.compare_digest(given, token):
                return JSONResponse({"message": "Session invalide."}, status_code=401)
            response = RedirectResponse("/", status_code=303)
            response.set_cookie(COOKIE, token, httponly=True, samesite="strict", path="/")
            return response

        if _protected(request.url.path):
            cookie = request.cookies.get(COOKIE, "")
            if not secrets.compare_digest(cookie, token):
                return JSONResponse(
                    {"message": "Session expirée. Relance l'application."}, status_code=401
                )
        return await call_next(request)

    return middleware
