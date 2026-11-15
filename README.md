# test-url-shorty

A small URL shortener in Python. It uses only the standard library (Python 3.10+) and stores links in SQLite.

## Run

```
python -m shortener --port 8000 --db links.db
```

Open http://127.0.0.1:8000 for a form, or use the API. Pass `--base-url https://sho.rt` when the server sits behind a proxy or a public domain, so that short links are built from that address.

## API

| Request | Result |
| --- | --- |
| `POST /api/shorten` with `{"url": "https://...", "alias": "optional"}` | `201` with `code`, `short_url`, `url`, `created_at`, `clicks` |
| `GET /<code>` | `302` redirect to the original URL, and counts the click |
| `GET /api/links/<code>` | `200` with the link and its click count |

```
curl -X POST localhost:8000/api/shorten -H "Content-Type: application/json" -d '{"url": "https://example.com/long/path"}'
```

Errors come back as `{"error": "..."}` with status `400` (invalid URL or alias), `404` (unknown code), `409` (alias already taken) or `413` (body too large).

Only `http` and `https` URLs are accepted. Aliases are 3-32 characters from letters, digits, `-` and `_`.

## Test

```
python -m unittest discover -s tests
```
