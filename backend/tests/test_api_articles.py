import io
from datetime import timedelta

import pytest
from PIL import Image

from vto.api import uploads
from vto.core import storage
from vto.core.models import Listing

LISTING = Listing(title="Robe Zara M", description="Jolie robe")
TIMEOUT = 5


def jpeg(color="red") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 50), color).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def scened(data_dir, make_scene):
    make_scene("mannequin", order=1)
    make_scene("cintre", order=2)


def create(api, n_photos=1, **fields):
    files = [("photos", (f"p{i}.jpg", jpeg(), "image/jpeg")) for i in range(n_photos)]
    data = {"garment_type": "robe", **fields}
    return api.post("/api/articles", data=data, files=files)


def wait(api):
    assert api.app.state.queue.wait_idle(TIMEOUT)


def reviewed(api, fake):
    fake.json_responses.append(LISTING)
    article = create(api).json()
    wait(api)
    return api.get(f"/api/articles/{article['id']}").json()


def test_create_queues_and_processes(api, fake, scened):
    fake.json_responses.append(LISTING)
    r = create(api, n_photos=2, brand="Zara", price="12.5")
    assert r.status_code == 201
    article = r.json()
    assert article["status"] == "queued"
    assert article["photos"] == ["photos/001.jpg", "photos/002.jpg"]
    assert article["input"]["brand"] == "Zara" and article["input"]["price"] == 12.5
    wait(api)
    done = api.get(f"/api/articles/{article['id']}").json()
    assert done["status"] == "to_review"
    assert done["listing"]["title"] == "Robe Zara M"
    assert [s["scene"] for s in done["scenes"]] == ["mannequin", "cintre"]


def test_create_requires_photo(api, scened):
    r = api.post("/api/articles", data={"garment_type": "robe"})
    assert r.status_code in (400, 422)
    assert r.json()["message"]


def test_create_rejects_unknown_type(api, scened):
    r = create(api, garment_type="chapeau")
    assert r.status_code == 422


def test_create_rejects_bad_extension(api, scened):
    r = api.post(
        "/api/articles",
        data={"garment_type": "robe"},
        files=[("photos", ("virus.exe", b"MZ", "application/octet-stream"))],
    )
    assert r.status_code == 400
    assert "virus.exe" in r.json()["message"]


def test_create_rejects_fake_image(api, scened):
    r = api.post(
        "/api/articles",
        data={"garment_type": "robe"},
        files=[("photos", ("photo.jpg", b"pas une image", "image/jpeg"))],
    )
    assert r.status_code == 400


def test_create_rejects_too_big(api, scened, monkeypatch):
    monkeypatch.setattr(uploads, "MAX_BYTES", 100)
    r = create(api)
    assert r.status_code == 400
    assert "Mo" in r.json()["message"]
    assert storage.list_articles() == []


def test_list_newest_first_and_filter(api, fake, scened):
    first = reviewed(api, fake)
    a = storage.load(first["id"])
    a.created_at -= timedelta(minutes=1)
    storage.save(a)
    second = create(api).json()  # sans annonce scriptée → erreur
    wait(api)
    listed = api.get("/api/articles").json()
    assert [x["id"] for x in listed] == [second["id"], first["id"]]
    assert [x["id"] for x in api.get("/api/articles?status=to_review").json()] == [first["id"]]


def test_get_unknown_article(api):
    r = api.get("/api/articles/inconnu")
    assert r.status_code == 404 and r.json()["message"]


def test_review_edits_and_validation(api, fake, scened):
    art = reviewed(api, fake)
    url = f"/api/articles/{art['id']}"

    r = api.patch(f"{url}/listing", json={**LISTING.model_dump(), "title": "Nouveau titre"})
    assert r.status_code == 200 and r.json()["listing"]["title"] == "Nouveau titre"

    r = api.patch(f"{url}/scenes/cintre", json={"excluded": True})
    assert [s["excluded"] for s in r.json()["scenes"]] == [False, True]

    r = api.patch(f"{url}/input", json={"garment_type": "robe", "size": "M"})
    assert r.json()["input"]["size"] == "M"

    assert api.post(f"{url}/validate").json()["status"] == "validated"
    assert api.patch(f"{url}/listing", json=LISTING.model_dump()).status_code == 400
    assert api.post(f"{url}/validate").status_code == 409
    assert api.post(f"{url}/unvalidate").json()["status"] == "to_review"


def test_generate_single_scene(api, fake, scened):
    art = reviewed(api, fake)
    n_calls = len(fake.calls)
    r = api.post(f"/api/articles/{art['id']}/generate", json={"scenes": ["cintre"]})
    assert r.status_code == 200 and r.json()["status"] == "queued"
    wait(api)
    assert [c.kind for c in fake.calls[n_calls:]] == ["image"]


def test_generate_listing_only(api, fake, scened):
    art = reviewed(api, fake)
    n_calls = len(fake.calls)
    fake.json_responses.append(Listing(title="Autre", description="d"))
    api.post(f"/api/articles/{art['id']}/generate", json={"listing": True})
    wait(api)
    assert [c.kind for c in fake.calls[n_calls:]] == ["json"]
    assert api.get(f"/api/articles/{art['id']}").json()["listing"]["title"] == "Autre"


def test_generate_everything_without_body(api, fake, scened):
    art = reviewed(api, fake)
    n_calls = len(fake.calls)
    fake.json_responses.append(LISTING)
    api.post(f"/api/articles/{art['id']}/generate")
    wait(api)
    assert [c.kind for c in fake.calls[n_calls:]] == ["image", "image", "json"]


def test_generate_unknown_scene(api, fake, scened):
    art = reviewed(api, fake)
    r = api.post(f"/api/articles/{art['id']}/generate", json={"scenes": ["plage"]})
    assert r.status_code == 400


def test_cancel_and_delete(make_api, fake, scened):
    api = make_api(lambda k: fake, start_queue=False)
    art = create(api).json()
    url = f"/api/articles/{art['id']}"
    assert api.delete(url).status_code == 409
    assert api.post(f"{url}/cancel").json()["status"] == "draft"
    assert api.delete(url).status_code == 204
    assert api.get(url).status_code == 404


def test_serves_article_images(api, fake, scened):
    art = reviewed(api, fake)
    r = api.get(f"/files/articles/{art['id']}/photos/001.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert "no-cache" in r.headers["cache-control"]
    assert api.get(f"/files/articles/{art['id']}/generated/cintre.jpg").status_code == 200


@pytest.mark.parametrize(
    "path", ["article.json", "photos/absente.jpg", "..%2F..%2Fsettings.json", "%2E%2E/x.jpg"]
)
def test_files_refuses_non_images_and_escapes(api, fake, scened, path):
    art = reviewed(api, fake)
    assert api.get(f"/files/articles/{art['id']}/{path}").status_code == 404
