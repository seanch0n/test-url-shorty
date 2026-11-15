# test-url-shorty

A small URL shortener in Python (Flask + SQLite).

## Run

```sh
pip install -e ".[dev]"
flask --app "shorty.app:create_app()" run
```

```sh
curl -X POST localhost:5000/api/links -H 'Content-Type: application/json' \
     -d '{"url": "https://example.com/some/page?x=1"}'
# {"data": {"short_code": "aZ3k9Qx", "short_url": "http://localhost:5000/aZ3k9Qx", ...}}

curl -i localhost:5000/aZ3k9Qx   # 302 to the destination
```

Optional fields on `POST /api/links`: `alias` (3-32 chars of letters, digits, `-`, `_`) and `expires_at` (ISO 8601 with a timezone).

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `SHORTY_DATABASE_PATH` | `shorty.db` | SQLite database file |
| `SHORTY_DATABASE_TIMEOUT` | `2.0` | Seconds to wait for a database lock |
| `SHORTY_BASE_URL` | request host | Public base for returned short URLs; set this in production |

## Test

```sh
python -m pytest
```
