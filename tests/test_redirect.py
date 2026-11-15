from datetime import datetime, timedelta, timezone

import pytest

import shorty.app as app_module
from shorty.app import create_app, get_repo
from shorty.config import DatabaseConfig


@pytest.fixture
def app(tmp_path):
    return create_app(DatabaseConfig(path=str(tmp_path / "r.db")), base_url="https://sho.rt")


@pytest.fixture
def client(app):
    return app.test_client()


def shorten(client, url, **extra):
    resp = client.post("/api/links", json={"url": url, **extra})
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["data"]["short_code"]


def test_redirects_with_302(client):
    code = shorten(client, "https://example.com/")
    resp = client.get(f"/{code}")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "https://example.com/"
    assert resp.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/a/b/c.html?x=1&y=two&y=three#section-2",
        "https://example.com/search?q=a+b&redirect=%2Fhome%3Fx%3D1",
        "http://example.com:8080/path%20with%20spaces/?empty=&flag",
    ],
)
def test_destination_path_and_query_preserved(client, url):
    code = shorten(client, url)
    assert client.get(f"/{code}").headers["Location"] == url


def test_non_ascii_destination_is_percent_encoded(client):
    code = shorten(client, "https://example.com/café?q=naïve")
    loc = client.get(f"/{code}").headers["Location"]
    assert loc == "https://example.com/caf%C3%A9?q=na%C3%AFve"


def test_alias_redirects(client):
    shorten(client, "https://example.com/promo", alias="spring-sale")
    assert client.get("/spring-sale").headers["Location"] == "https://example.com/promo"


def test_short_codes_are_case_sensitive(client):
    code = shorten(client, "https://example.com", alias="CaseCode")
    assert client.get("/CaseCode").status_code == 302
    assert client.get("/casecode").status_code == 404


def test_unknown_code_returns_404(client):
    resp = client.get("/zzzzzzz")
    assert resp.status_code == 404
    assert resp.get_json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("path", ["/favicon.ico", "/a.b", "/x", "/" + "a" * 40])
def test_impossible_codes_skip_the_database(client, monkeypatch, path):
    def fail():
        raise AssertionError("database should not be touched")

    monkeypatch.setattr(app_module, "get_repo", fail)
    resp = client.get(path)
    assert resp.status_code == 404
    assert resp.get_json()["error"]["code"] == "not_found"


def test_expired_link_cannot_be_used(app, client):
    soon = datetime.now(timezone.utc) + timedelta(seconds=60)
    code = shorten(client, "https://example.com", expires_at=soon.isoformat())
    assert client.get(f"/{code}").status_code == 302

    with app.app_context():
        conn = get_repo().conn
        with conn:
            conn.execute(
                "UPDATE links SET expires_at = ? WHERE short_code = ?",
                ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), code),
            )
    resp = client.get(f"/{code}")
    assert resp.status_code == 410
    assert resp.get_json()["error"]["code"] == "link_expired"
    assert "Location" not in resp.headers


def test_disabled_link_cannot_be_used(app, client):
    code = shorten(client, "https://example.com")
    with app.app_context():
        assert get_repo().set_disabled(code)
    resp = client.get(f"/{code}")
    assert resp.status_code == 410
    assert resp.get_json()["error"]["code"] == "link_disabled"
    assert "Location" not in resp.headers


def test_redirect_does_one_read_and_no_writes(app, client):
    code = shorten(client, "https://example.com")
    statements = []
    real_connect = app_module.connect

    def traced_connect(config):
        conn = real_connect(config)
        conn.set_trace_callback(statements.append)
        return conn

    app_module.connect = traced_connect
    try:
        assert client.get(f"/{code}").status_code == 302
    finally:
        app_module.connect = real_connect
    queries = [s for s in statements if not s.upper().startswith("PRAGMA")]
    assert len(queries) == 1 and queries[0].upper().startswith("SELECT")


def test_api_routes_are_not_short_codes(client):
    assert client.get("/api").status_code == 404
    assert client.get("/api/links").status_code == 405
