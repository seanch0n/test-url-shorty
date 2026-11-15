# test-url-shorty

A small URL shortener in Python, built on FastAPI with links stored in SQLite.

## Install

Python 3.10 or newer.

```
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```
python -m shorty --port 8000 --db links.db
```

Open http://127.0.0.1:8000/docs for an interactive page where you can try the API.

| Option | Environment variable | Default |
| --- | --- | --- |
| `--host` | | `127.0.0.1` |
| `--port` | | `8000` |
| `--db` | `SHORTY_DB` | `links.db` |
| `--base-url` | `SHORTY_BASE_URL` | the address the request came in on |

Set the base URL (for example `https://sho.rt`) when the server sits behind a proxy or a public domain, so that short links are built from that address.

## API

| Request | Result |
| --- | --- |
| `POST /api/links` with `{"url": "https://...", "alias": "optional"}` | `201` with `code`, `short_url`, `url`, `created_at`, `clicks` |
| `GET /<code>` | `302` redirect to the original URL, and counts the click |
| `GET /api/links/<code>` | `200` with the link and its click count |

```
curl -X POST localhost:8000/api/links -H "Content-Type: application/json" -d '{"url": "https://example.com/long/path"}'
```

Errors come back as `{"detail": "..."}` with status `400` (invalid URL or alias), `404` (unknown code), `409` (alias already taken) or `422` (malformed request body).

Only `http` and `https` URLs up to 2048 characters are accepted. Aliases are 3-32 characters from letters, digits, `-` and `_`. Shortening the same URL twice gives two separate codes, each with its own click count.

## Test

```
python -m pytest
```
