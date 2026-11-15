## Summary

Adds `POST /api/links` (#3), the first HTTP endpoint: it validates a destination URL, allows only http and https, picks a short code through #15's service, saves it and returns the full short URL. Responses share one JSON shape, `{"data": ...}` or `{"error": {"code", "message"}}`. Stacked on #15, so this diff shows only the API layer.

## Flow

{{flow}}

## How to review

1. {{file:shorty/validation.py:19}} — `validate_destination_url`. Check the scheme allowlist and which malformed URLs get through.
2. {{file:shorty/app.py:73}} — `create_link`. Check that each failure maps to the right status and error code.
3. {{file:shorty/app.py:80}} — the optional `alias` and `expires_at` fields, which go slightly beyond the issue (D4). Decide whether to keep them.
4. {{file:shorty/app.py:32}} — `short_url_for`. Note the Host-header fallback when `SHORTY_BASE_URL` is unset.
5. {{file:shorty/app.py:50}} — the app factory: migrations at startup and one connection per request, closed in teardown.
6. {{file:tests/test_api.py:1}} — valid, invalid and unsupported inputs, plus the error-envelope check.

## Decisions

Each decision below is also an inline comment on the code it affected. Reply on the thread to discuss; run `/pr-kit:address-review` to pull replies back into the authoring session.

{{decisions}}

## Testing

`python -m pytest -q`: 70 passed, 36 of them API tests via Flask's test client. Not tested under a production WSGI server.
