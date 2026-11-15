import http.client
import json
import threading
import unittest

from shortener import AliasTaken, InvalidAlias, InvalidURL, LinkStore, make_server
from shortener.store import CODE_LENGTH


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.store = LinkStore()
        self.addCleanup(self.store.close)

    def test_create_and_resolve(self):
        link = self.store.create("https://example.com/page?q=1")
        self.assertEqual(len(link.code), CODE_LENGTH)
        self.assertEqual(self.store.resolve(link.code), "https://example.com/page?q=1")

    def test_resolve_counts_clicks(self):
        link = self.store.create("https://example.com")
        self.store.resolve(link.code)
        self.store.resolve(link.code)
        self.assertEqual(self.store.get(link.code).clicks, 2)

    def test_unknown_code(self):
        self.assertIsNone(self.store.resolve("missing"))
        self.assertIsNone(self.store.get("missing"))

    def test_same_url_gets_distinct_codes(self):
        first = self.store.create("https://example.com")
        second = self.store.create("https://example.com")
        self.assertNotEqual(first.code, second.code)

    def test_custom_alias(self):
        self.store.create("https://example.com", alias="my-link")
        self.assertEqual(self.store.resolve("my-link"), "https://example.com")
        with self.assertRaises(AliasTaken):
            self.store.create("https://example.org", alias="my-link")

    def test_invalid_aliases(self):
        for alias in ["ab", "has space", "a/b", "api", "x" * 33, 5]:
            with self.subTest(alias=alias), self.assertRaises(InvalidAlias):
                self.store.create("https://example.com", alias=alias)

    def test_invalid_urls(self):
        bad = [
            "",
            None,
            "example.com",
            "javascript:alert(1)",
            "ftp://example.com/file",
            "http://",
            "https://example.com/a b",
            "https://example.com/\r\nSet-Cookie: x=1",
            "https://bücher.example/",
            "http://[::1",
            "https://example.com/" + "a" * 2048,
        ]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(InvalidURL):
                self.store.create(url)

    def test_non_ascii_path_is_percent_encoded(self):
        link = self.store.create("https://example.com/café?q=a%20b")
        self.assertEqual(link.url, "https://example.com/caf%C3%A9?q=a%20b")


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.store = LinkStore()
        self.server = make_server(self.store, port=0)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.store.close)
        self.addCleanup(self.server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        self.addCleanup(conn.close)
        if body is not None and not isinstance(body, bytes):
            body = json.dumps(body).encode()
        conn.request(method, path, body=body)
        response = conn.getresponse()
        data = response.read()
        is_json = response.getheader("Content-Type") == "application/json"
        return response, json.loads(data) if is_json and data else data

    def test_shorten_redirect_and_stats(self):
        response, created = self.request(
            "POST", "/api/shorten", {"url": "https://example.com/long"}
        )
        self.assertEqual(response.status, 201)
        port = self.server.server_port
        self.assertEqual(created["short_url"], f"http://127.0.0.1:{port}/{created['code']}")

        response, _ = self.request("GET", f"/{created['code']}")
        self.assertEqual(response.status, 302)
        self.assertEqual(response.getheader("Location"), "https://example.com/long")

        response, stats = self.request("GET", f"/api/links/{created['code']}")
        self.assertEqual(response.status, 200)
        self.assertEqual(stats["clicks"], 1)
        self.assertEqual(stats["url"], "https://example.com/long")

    def test_alias_conflict(self):
        body = {"url": "https://example.com", "alias": "docs"}
        self.assertEqual(self.request("POST", "/api/shorten", body)[0].status, 201)
        response, data = self.request("POST", "/api/shorten", body)
        self.assertEqual(response.status, 409)
        self.assertIn("docs", data["error"])

    def test_bad_requests(self):
        cases = [
            ({"url": "javascript:alert(1)"}, 400),
            ({"alias": "docs"}, 400),
            ({"url": "https://example.com", "alias": "no"}, 400),
            (["https://example.com"], 400),
            (b"not json", 400),
            (b"x" * 20000, 413),
        ]
        for body, status in cases:
            with self.subTest(body=body):
                response, data = self.request("POST", "/api/shorten", body)
                self.assertEqual(response.status, status)
                self.assertIn("error", data)

    def test_not_found(self):
        self.assertEqual(self.request("GET", "/nope123")[0].status, 404)
        self.assertEqual(self.request("GET", "/api/links/nope123")[0].status, 404)
        self.assertEqual(self.request("POST", "/elsewhere", {})[0].status, 404)

    def test_index_page(self):
        response, body = self.request("GET", "/")
        self.assertEqual(response.status, 200)
        self.assertIn(b"<form", body)

    def test_base_url_override(self):
        server = make_server(self.store, port=0, base_url="https://sho.rt/")
        handler = server.RequestHandlerClass
        server.server_close()
        self.assertEqual(handler.base_url, "https://sho.rt/")


if __name__ == "__main__":
    unittest.main()
