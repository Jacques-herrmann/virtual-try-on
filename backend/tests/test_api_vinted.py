from datetime import UTC, datetime

import pytest
from test_api_articles import LISTING, create, reviewed, wait

from fakes import FakeVintedWorker
from samples import loaded_data
from vto.core import config, paths, storage
from vto.core.models import ArticleStatus as S
from vto.core.models import VintedResult


@pytest.fixture
def worker():
    return FakeVintedWorker(loaded_data())


@pytest.fixture
def vapi(make_api, fake, worker):
    return make_api(lambda key: fake, vinted_worker=worker)


@pytest.fixture
def scened(data_dir, make_scene):
    make_scene("mannequin", order=1)
    make_scene("cintre", order=2)


def validated(api, fake):
    article = reviewed(api, fake)
    return api.post(f"/api/articles/{article['id']}/validate").json()


# --- /api/vinted/* -----------------------------------------------------------------------


def test_status(vapi):
    body = vapi.get("/api/vinted/status").json()
    assert body["data_revision"] == "r1" and body["data_source"] == "bundled"
    assert body["batch"]["running"] is False
    assert {"connected", "connecting"} <= body.keys()


@pytest.mark.parametrize("command", ["connect", "disconnect", "stop"])
def test_simple_commands(vapi, worker, command):
    r = vapi.post(f"/api/vinted/{command}")
    assert r.status_code == (202 if command == "connect" else 200)
    assert worker.commands == [(command,)]
    assert "batch" in r.json()


@pytest.mark.parametrize("command", ["connect", "disconnect"])
def test_busy_is_409(vapi, worker, command):
    worker.busy = True
    r = vapi.post(f"/api/vinted/{command}")
    assert r.status_code == 409
    assert "déjà en cours" in r.json()["message"]


def test_send(vapi, fake, worker, scened):
    a, b = validated(vapi, fake), validated(vapi, fake)
    r = vapi.post("/api/vinted/send", json={"article_ids": [a["id"], b["id"]]})
    assert r.status_code == 202
    assert worker.commands == [("send", [a["id"], b["id"]])]


def test_send_while_running_is_409(vapi, fake, worker, scened):
    a = validated(vapi, fake)
    worker.busy = True
    assert vapi.post("/api/vinted/send", json={"article_ids": [a["id"]]}).status_code == 409


def test_send_refused_when_update_required(vapi, fake, worker, scened):
    a = validated(vapi, fake)
    worker.update_required = True
    r = vapi.post("/api/vinted/send", json={"article_ids": [a["id"]]})
    assert r.status_code == 409
    assert "Mets l'application à jour" in r.json()["message"]
    assert worker.commands == []


def test_send_requires_validated_articles(vapi, fake, worker, scened):
    a = validated(vapi, fake)
    b = reviewed(vapi, fake)
    r = vapi.post("/api/vinted/send", json={"article_ids": [a["id"], b["id"]]})
    assert r.status_code == 422
    assert "validé" in r.json()["message"]
    assert worker.commands == []


@pytest.mark.parametrize("body", [{"article_ids": []}, {}])
def test_send_requires_articles(vapi, body):
    assert vapi.post("/api/vinted/send", json=body).status_code == 422


def test_send_unknown_article_is_404(vapi):
    assert vapi.post("/api/vinted/send", json={"article_ids": ["nope"]}).status_code == 404


def published(api, fake, url="https://www.vinted.fr/items/42"):
    article = storage.load(validated(api, fake)["id"])
    storage.record_vinted(
        article, VintedResult(mode="draft", status="ok", url=url, sent_at=datetime.now(UTC))
    )
    return article


def test_open(vapi, fake, worker, scened):
    article = published(vapi, fake)
    r = vapi.post("/api/vinted/open", json={"article_id": article.id})
    assert r.status_code == 200
    assert worker.commands == [("open", "https://www.vinted.fr/items/42")]


def test_open_requires_a_vinted_url(vapi, fake, worker, scened):
    article = validated(vapi, fake)
    r = vapi.post("/api/vinted/open", json={"article_id": article["id"]})
    assert r.status_code == 400
    assert worker.commands == []


def test_open_refuses_foreign_url(vapi, fake, worker, scened):
    article = published(vapi, fake, url="https://exemple.com/piege")
    assert vapi.post("/api/vinted/open", json={"article_id": article.id}).status_code == 400
    assert worker.commands == []


def test_catalog(vapi):
    body = vapi.get("/api/vinted/catalog").json()
    assert body["revision"] == "r1"
    femmes = body["catalog"][0]
    assert femmes["label"] == "Femmes"
    assert femmes["children"][0] == {
        "id": 1779, "label": "Robes", "children": [], "size_group": "4"
    }
    assert body["size_groups"] == {"4": ["XS", "S", "M"]}
    assert body["colors"] == ["Noir", "Blanc"]
    assert body["conditions"] == ["Neuf", "Bon état"]
    assert body["parcel_sizes"] == ["Petit"]


def test_catalog_unavailable(make_api, fake):
    api = make_api(lambda key: fake, vinted_worker=FakeVintedWorker(loaded=None))
    r = api.get("/api/vinted/catalog")
    assert r.status_code == 503
    assert "indisponible" in r.json()["message"]


# --- Articles ----------------------------------------------------------------------------


def test_article_exposes_gallery_and_vinted(vapi, fake, scened):
    article = reviewed(vapi, fake)
    assert article["gallery"] is None and article["vinted"] is None
    assert article["effective_gallery"] == [
        "generated/mannequin.jpg", "generated/cintre.jpg"
    ]
    listed = vapi.get("/api/articles").json()[0]
    assert "effective_gallery" in listed


def test_patch_gallery(vapi, fake, scened):
    article = reviewed(vapi, fake)
    order = ["photos/001.jpg", "generated/cintre.jpg"]
    r = vapi.patch(f"/api/articles/{article['id']}/gallery", json={"gallery": order})
    assert r.status_code == 200
    assert r.json()["gallery"] == order and r.json()["effective_gallery"] == order
    r = vapi.patch(f"/api/articles/{article['id']}/gallery", json={"gallery": None})
    assert r.json()["gallery"] is None


@pytest.mark.parametrize(
    "gallery",
    [[], ["generated/cintre.jpg", "generated/cintre.jpg"], ["../x.jpg"], ["photos/9.jpg"]],
)
def test_patch_gallery_refused(vapi, fake, scened, gallery):
    article = reviewed(vapi, fake)
    r = vapi.patch(f"/api/articles/{article['id']}/gallery", json={"gallery": gallery})
    assert r.status_code == 400
    assert r.json()["message"]


def listing_body(**changes):
    return {**LISTING.model_dump(mode="json"), **changes}


def test_patch_listing_with_known_category(vapi, fake, scened):
    article = reviewed(vapi, fake)
    r = vapi.patch(
        f"/api/articles/{article['id']}/listing",
        json=listing_body(category="1779", color=["Noir", "Blanc"]),
    )
    assert r.status_code == 200
    assert r.json()["listing"]["category"] == "1779"
    assert r.json()["listing"]["color"] == ["Noir", "Blanc"]


@pytest.mark.parametrize(
    "changes",
    [
        {"category": "999"},  # inconnue
        {"category": "1904"},  # pas une feuille
        {"color": ["Noir", "Blanc", "Gris"]},
    ],
)
def test_patch_listing_refused(vapi, fake, scened, changes):
    article = reviewed(vapi, fake)
    r = vapi.patch(f"/api/articles/{article['id']}/listing", json=listing_body(**changes))
    assert r.status_code == 422
    assert r.json()["message"]


def test_generation_uses_vinted_choices(vapi, fake, scened):
    fake.json_responses.append(LISTING)
    article = create(vapi, garment_type="robe", audience="femme").json()
    wait(vapi)
    schema = fake.calls[-1].schema
    category = schema.model_json_schema()["properties"]["category"]
    assert {"enum": ["1779"], "type": "string"} in category["anyOf"]
    assert vapi.get(f"/api/articles/{article['id']}").json()["status"] == "to_review"


def test_generation_without_vinted_data_is_free(make_api, fake, scened):
    api = make_api(lambda key: fake, vinted_worker=FakeVintedWorker(loaded=None))
    fake.json_responses.append(LISTING)
    create(api)
    wait(api)
    assert fake.calls[-1].schema.__name__ == "Listing"


# --- Réglages ----------------------------------------------------------------------------


def test_settings_vinted_mode(vapi):
    assert vapi.get("/api/settings").json()["vinted_mode"] == "draft"
    r = vapi.put("/api/settings", json={"vinted_mode": "publish"})
    assert r.status_code == 200 and r.json()["vinted_mode"] == "publish"
    assert config.load_settings().vinted_mode == "publish"


def test_settings_rejects_unknown_vinted_mode(vapi):
    assert vapi.put("/api/settings", json={"vinted_mode": "auto"}).status_code == 422


def test_published_article_status(vapi, fake, scened):
    article = published(vapi, fake)
    body = vapi.get(f"/api/articles/{article.id}").json()
    assert body["status"] == S.PUBLISHED.value
    assert body["vinted"]["url"] == "https://www.vinted.fr/items/42"
    assert paths.article_dir(article.id).is_dir()
