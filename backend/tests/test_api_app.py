import logging

import pytest
from fastapi import APIRouter

from conftest import API_PORT, API_TOKEN
from vto.core import errors


def test_login_sets_strict_http_only_cookie(make_api, fake):
    client = make_api(lambda k: fake, login=False)
    r = client.get("/api/session", params={"token": API_TOKEN}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    cookie = r.headers["set-cookie"].lower()
    assert "vto_session=" in cookie and "httponly" in cookie and "samesite=strict" in cookie


def test_wrong_token_refused(make_api, fake):
    client = make_api(lambda k: fake, login=False)
    r = client.get("/api/session", params={"token": "faux"}, follow_redirects=False)
    assert r.status_code == 401
    assert "vto_session" not in r.headers.get("set-cookie", "")


@pytest.mark.parametrize("path", ["/api/queue", "/files/articles/x/photos/001.jpg"])
def test_protected_routes_need_cookie(make_api, fake, path):
    client = make_api(lambda k: fake, login=False)
    r = client.get(path)
    assert r.status_code == 401
    assert r.json()["message"]


def test_forged_cookie_refused(make_api, fake):
    client = make_api(lambda k: fake, login=False)
    client.cookies.set("vto_session", "autre")
    assert client.get("/api/queue").status_code == 401


def test_health_is_public(make_api, fake):
    client = make_api(lambda k: fake, login=False)
    assert client.get("/api/health").json() == {"ok": True}


def test_foreign_host_refused(api):
    r = api.get("/api/queue", headers={"host": "evil.example:80"})
    assert r.status_code == 400
    r = api.get("/api/health", headers={"host": f"localhost.evil.example:{API_PORT}"})
    assert r.status_code == 400


def test_logged_in_client_reaches_api(api):
    assert api.get("/api/queue").status_code == 200


@pytest.fixture
def raising_api(api):
    router = APIRouter()

    @router.get("/api/test/{kind}")
    def boom(kind: str, n: int = 0):
        raise {
            "notfound": errors.ArticleNotFound("x"),
            "transition": errors.InvalidTransition("draft", "published"),
            "vto": errors.InvalidApiKey(),
            "crash": RuntimeError("détail technique secret"),
        }[kind]

    api.app.include_router(router)
    # Avant la route attrape-tout du front.
    api.app.router.routes.insert(0, api.app.router.routes.pop())
    return api


@pytest.mark.parametrize(
    ("kind", "status"), [("notfound", 404), ("transition", 409), ("vto", 400), ("crash", 500)]
)
def test_error_mapping(raising_api, kind, status, caplog):
    caplog.set_level(logging.ERROR)
    r = raising_api.get(f"/api/test/{kind}")
    assert r.status_code == status
    message = r.json()["message"]
    assert message and "secret" not in message
    if kind == "crash":
        assert "secret" in caplog.text


def test_validation_error_in_french(raising_api):
    r = raising_api.get("/api/test/vto", params={"n": "pas un nombre"})
    assert r.status_code == 422
    assert r.json()["message"] == "Requête invalide."


def test_without_built_front(make_api, fake, tmp_path):
    client = make_api(lambda k: fake, static_dir=tmp_path / "absent")
    r = client.get("/")
    assert r.status_code == 200 and "npm run build" in r.text


def test_serves_built_front_and_spa_routes(make_api, fake, tmp_path):
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<div id=app></div>", encoding="utf-8")
    (static / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    client = make_api(lambda k: fake, static_dir=static)
    assert client.get("/").text == "<div id=app></div>"
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/articles/123").text == "<div id=app></div>"
    assert client.get("/api/inconnue").status_code == 404
    assert client.get("/../../etc/passwd").text == "<div id=app></div>"
