import pytest
from fastapi.testclient import TestClient

from shorty.app import create_app
from shorty.store import ALPHABET, CODE_LENGTH, InvalidURL, LinkStore, validate_url


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "links.db"))
    return TestClient(app, follow_redirects=False)


def shorten(client, url="https://example.com/a/long/path?q=1", **extra):
    return client.post("/api/links", json={"url": url, **extra})


def test_shorten_then_redirect(client):
    created = shorten(client)
    assert created.status_code == 201
    body = created.json()
    assert len(body["code"]) == CODE_LENGTH
    assert set(body["code"]) <= set(ALPHABET)
    assert body["short_url"] == f"http://testserver/{body['code']}"
    assert body["clicks"] == 0

    resp = client.get(f"/{body['code']}")
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://example.com/a/long/path?q=1"


def test_clicks_are_counted(client):
    code = shorten(client).json()["code"]
    for _ in range(3):
        client.get(f"/{code}")
    info = client.get(f"/api/links/{code}")
    assert info.status_code == 200
    assert info.json()["clicks"] == 3


def test_same_url_gets_distinct_codes(client):
    assert shorten(client).json()["code"] != shorten(client).json()["code"]


def test_custom_alias(client):
    assert shorten(client, alias="my-link").json()["code"] == "my-link"
    assert client.get("/my-link").status_code == 302
    assert shorten(client, alias="my-link").status_code == 409


@pytest.mark.parametrize("alias", ["ab", "has space", "a/b", "x" * 33, "docs", "API"])
def test_bad_alias_rejected(client, alias):
    assert shorten(client, alias=alias).status_code == 400


@pytest.mark.parametrize(
    "url",
    [
        "",
        "example.com",
        "ftp://example.com/file",
        "javascript:alert(1)",
        "http://",
        "https://exa mple.com",
        "https://example.com/\nX-Injected: 1",
        "https://example.com/" + "a" * 2048,
    ],
)
def test_bad_url_rejected(client, url):
    assert shorten(client, url).status_code == 400


def test_missing_url_field(client):
    assert client.post("/api/links", json={}).status_code == 422


def test_unknown_code(client):
    assert client.get("/nope123").status_code == 404
    assert client.get("/api/links/nope123").status_code == 404


def test_base_url_override(tmp_path):
    app = create_app(str(tmp_path / "links.db"), base_url="https://sho.rt/")
    body = shorten(TestClient(app), alias="abc").json()
    assert body["short_url"] == "https://sho.rt/abc"


def test_docs_still_reachable(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/").headers["location"] == "/docs"


def test_links_survive_reopen(tmp_path):
    path = str(tmp_path / "links.db")
    code = LinkStore(path).create("https://example.com").code
    assert LinkStore(path).get(code).url == "https://example.com"


def test_validate_url_trims():
    assert validate_url("  https://example.com/x ") == "https://example.com/x"
    with pytest.raises(InvalidURL):
        validate_url("https://[bad")
