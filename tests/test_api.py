import pytest

from shorty.app import create_app
from shorty.config import DatabaseConfig


@pytest.fixture
def app(tmp_path):
    return create_app(DatabaseConfig(path=str(tmp_path / "api.db")), base_url="https://sho.rt")


@pytest.fixture
def client(app):
    return app.test_client()


def post(client, payload):
    return client.post("/api/links", json=payload)


def assert_error(resp, status, code):
    assert resp.status_code == status, resp.get_json()
    body = resp.get_json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]


def test_shortens_valid_url(client):
    resp = post(client, {"url": "https://example.com/path?q=1#frag"})
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["url"] == "https://example.com/path?q=1#frag"
    assert len(data["short_code"]) == 7
    assert data["short_url"] == f"https://sho.rt/{data['short_code']}"
    assert data["created_at"].endswith("Z")
    assert data["expires_at"] is None


def test_http_is_allowed(client):
    assert post(client, {"url": "http://example.com"}).status_code == 201


def test_short_url_falls_back_to_request_host(tmp_path):
    client = create_app(DatabaseConfig(path=str(tmp_path / "h.db")), base_url="").test_client()
    data = post(client, {"url": "https://example.com"}).get_json()["data"]
    assert data["short_url"] == f"http://localhost/{data['short_code']}"


def test_link_is_persisted(app, client):
    from shorty.app import get_repo

    code = post(client, {"url": "https://example.com"}).get_json()["data"]["short_code"]
    with app.app_context():
        assert get_repo().get_by_code(code).target_url == "https://example.com"


def test_duplicate_destinations_get_distinct_codes(client):
    a = post(client, {"url": "https://same.example"}).get_json()["data"]
    b = post(client, {"url": "https://same.example"}).get_json()["data"]
    assert a["short_code"] != b["short_code"]


@pytest.mark.parametrize(
    "url",
    [None, "", "   ", 123, "example.com", "https://", "https:///path", "http://exa mple.com",
     "https://example.com:99999", "https://exa\nmple.com", "https://" + "a" * 2048],
)
def test_invalid_urls_rejected(client, url):
    assert_error(post(client, {"url": url}), 400, "invalid_url")


@pytest.mark.parametrize(
    "url", ["ftp://example.com/file", "javascript:alert(1)", "file:///etc/passwd",
            "mailto:a@b.example", "data:text/html,hi"],
)
def test_unsupported_protocols_rejected(client, url):
    assert_error(post(client, {"url": url}), 400, "unsupported_scheme")


def test_scheme_check_is_case_insensitive(client):
    assert post(client, {"url": "HTTPS://example.com"}).status_code == 201
    assert_error(post(client, {"url": "JavaScript:alert(1)"}), 400, "unsupported_scheme")


@pytest.mark.parametrize("body", ["not json", "[1, 2]", "null"])
def test_non_object_body_rejected(client, body):
    resp = client.post("/api/links", data=body, content_type="application/json")
    assert_error(resp, 400, "invalid_json")


def test_custom_alias(client):
    resp = post(client, {"url": "https://example.com", "alias": "my-promo"})
    assert resp.status_code == 201
    assert resp.get_json()["data"]["short_url"] == "https://sho.rt/my-promo"


def test_taken_alias_conflicts(client):
    post(client, {"url": "https://a.example", "alias": "promo"})
    assert_error(post(client, {"url": "https://b.example", "alias": "promo"}), 409, "alias_taken")


@pytest.mark.parametrize("alias", ["a", "api", "bad alias", 42])
def test_invalid_alias_rejected(client, alias):
    assert_error(post(client, {"url": "https://a.example", "alias": alias}), 400, "invalid_alias")


def test_expires_at(client):
    resp = post(client, {"url": "https://a.example", "expires_at": "2030-01-01T00:00:00+02:00"})
    assert resp.status_code == 201
    assert resp.get_json()["data"]["expires_at"] == "2029-12-31T22:00:00Z"


@pytest.mark.parametrize("value", ["tomorrow", "2030-01-01T00:00:00", 1700000000])
def test_invalid_expires_at_rejected(client, value):
    assert_error(post(client, {"url": "https://a.example", "expires_at": value}), 400, "invalid_expires_at")


def test_wrong_method_uses_error_format(client):
    assert_error(client.get("/api/links"), 405, "method_not_allowed")
