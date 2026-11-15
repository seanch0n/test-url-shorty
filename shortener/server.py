"""HTTP front end for the URL shortener."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .store import ALIAS_RE, AliasTaken, InvalidAlias, InvalidURL, LinkStore

MAX_BODY_BYTES = 16 * 1024

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>URL shortener</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 36rem; margin: 4rem auto; padding: 0 1rem; }
  form { display: grid; gap: .75rem; }
  input, button { font: inherit; padding: .5rem; }
  #result { margin-top: 1.5rem; }
  .error { color: #b00020; }
</style>
</head>
<body>
<h1>URL shortener</h1>
<form id="form">
  <input name="url" type="url" placeholder="https://example.com/a/very/long/link" required>
  <input name="alias" placeholder="Custom alias (optional)" pattern="[A-Za-z0-9_-]{3,32}">
  <button>Shorten</button>
</form>
<p id="result"></p>
<script>
const form = document.getElementById("form");
const result = document.getElementById("result");
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = { url: form.url.value };
  if (form.alias.value) body.alias = form.alias.value;
  const response = await fetch("/api/shorten", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  result.textContent = "";
  result.className = response.ok ? "" : "error";
  if (response.ok) {
    const link = document.createElement("a");
    link.href = link.textContent = data.short_url;
    result.append(link);
  } else {
    result.textContent = data.error;
  }
});
</script>
</body>
</html>
"""


class ShortenerHandler(BaseHTTPRequestHandler):
    store: LinkStore
    base_url: str | None = None
    server_version = "shortener"

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            self._send(HTTPStatus.OK, INDEX_HTML.encode(), "text/html; charset=utf-8")
        elif path.startswith("/api/links/"):
            link = self.store.get(path.removeprefix("/api/links/"))
            if link is None:
                self._error(HTTPStatus.NOT_FOUND, "no such link")
            else:
                self._json(HTTPStatus.OK, self._describe(link))
        elif ALIAS_RE.fullmatch(path[1:]) and (url := self.store.resolve(path[1:])):
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", url)
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self._error(HTTPStatus.NOT_FOUND, "not found")

    do_HEAD = do_GET

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/shorten":
            self._error(HTTPStatus.NOT_FOUND, "not found")
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._error(HTTPStatus.LENGTH_REQUIRED, "Content-Length is required")
            return
        if not 0 <= length <= MAX_BODY_BYTES:
            self.close_connection = True
            self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request body too large")
            return
        try:
            body = json.loads(self.rfile.read(length))
        except ValueError:
            self._error(HTTPStatus.BAD_REQUEST, "body must be JSON")
            return
        if not isinstance(body, dict):
            self._error(HTTPStatus.BAD_REQUEST, "body must be a JSON object")
            return
        try:
            link = self.store.create(body.get("url"), body.get("alias"))
        except (InvalidURL, InvalidAlias) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))
        except AliasTaken as exc:
            self._error(HTTPStatus.CONFLICT, str(exc))
        else:
            self._json(HTTPStatus.CREATED, self._describe(link))

    def _describe(self, link) -> dict:
        base = self.base_url or f"http://{self.headers.get('Host', 'localhost')}"
        return {**link.to_dict(), "short_url": f"{base.rstrip('/')}/{link.code}"}

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json(status, {"error": message})

    def _json(self, status: HTTPStatus, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json")

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)


def make_server(
    store: LinkStore,
    host: str = "127.0.0.1",
    port: int = 8000,
    base_url: str | None = None,
) -> ThreadingHTTPServer:
    handler = type(
        "Handler", (ShortenerHandler,), {"store": store, "base_url": base_url}
    )
    return ThreadingHTTPServer((host, port), handler)
