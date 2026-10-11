from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from vto.core import storage
from vto.core.errors import VtoError
from vto.core.models import Article, ArticleStatus, ListingChoices
from vto.vinted.catalog import Catalog
from vto.vinted.schema import CategoryNode
from vto.vinted.worker import DATA_UNAVAILABLE_MESSAGE

router = APIRouter(prefix="/api/vinted")

DATA_WAIT = 10.0  # s : premier chargement des données au démarrage


class SendRequest(BaseModel):
    article_ids: list[str] = Field(min_length=1)


class OpenRequest(BaseModel):
    article_id: str


def current_catalog(app: FastAPI) -> Catalog | None:
    """Catalogue des données Vinted chargées, recalculé seulement quand elles changent."""
    loaded = app.state.vinted.loaded
    if loaded is None:
        return None
    cached = getattr(app.state, "vinted_catalog", None)
    if cached is None or cached[0] is not loaded:
        cached = (loaded, Catalog(loaded.data))
        app.state.vinted_catalog = cached
    return cached[1]


def require_catalog(app: FastAPI) -> Catalog:
    app.state.vinted.wait_loaded(DATA_WAIT)
    catalog = current_catalog(app)
    if catalog is None:
        raise HTTPException(503, DATA_UNAVAILABLE_MESSAGE)
    return catalog


def choices_provider(app: FastAPI):
    def choices_for(article: Article) -> ListingChoices | None:
        catalog = current_catalog(app)
        return catalog.choices_for(article) if catalog else None

    return choices_for


def _status(request: Request) -> dict:
    return request.app.state.vinted.status()


@router.get("/status")
def status(request: Request) -> dict:
    return _status(request)


@router.post("/connect", status_code=202)
def connect(request: Request) -> dict:
    request.app.state.vinted.connect()
    return _status(request)


@router.post("/disconnect")
def disconnect(request: Request) -> dict:
    request.app.state.vinted.disconnect()
    return _status(request)


@router.post("/stop")
def stop(request: Request) -> dict:
    request.app.state.vinted.stop()
    return _status(request)


@router.post("/send", status_code=202)
def send(request: Request, body: SendRequest):
    articles = [storage.load(article_id) for article_id in body.article_ids]
    pending = [a for a in articles if a.status != ArticleStatus.VALIDATED]
    if pending:
        names = ", ".join(f"« {a.listing.title if a.listing else a.id} »" for a in pending)
        return JSONResponse(
            {"message": f"Seuls les articles validés peuvent être envoyés : {names}."},
            status_code=422,
        )
    request.app.state.vinted.send(body.article_ids)
    return _status(request)


@router.post("/open")
def open_on_vinted(request: Request, body: OpenRequest) -> dict:
    article = storage.load(body.article_id)
    url = article.vinted.url if article.vinted else None
    catalog = current_catalog(request.app)
    home = catalog.data.urls.home if catalog else "https://www.vinted.fr"
    if not url or not url.startswith(home.rstrip("/") + "/"):
        raise VtoError("Cet article n'a pas encore d'annonce sur Vinted.")
    request.app.state.vinted.open_url(url)
    return _status(request)


def _tree(node: CategoryNode) -> dict:
    """Nœud pour l'interface : sans les types de vêtement (utiles à Gemini seulement)."""
    tree = {"id": node.id, "label": node.label, "children": [_tree(c) for c in node.children]}
    if node.size_group is not None:
        tree["size_group"] = node.size_group
    return tree


@router.get("/catalog")
def catalog(request: Request) -> dict:
    data = require_catalog(request.app).data
    return {
        "revision": data.revision,
        "catalog": [_tree(node) for node in data.catalog],
        "size_groups": data.size_groups,
        "colors": data.colors,
        "conditions": list(data.conditions),
        "parcel_sizes": list(data.parcel_sizes),
    }
