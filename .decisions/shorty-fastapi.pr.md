## Summary

Adds a URL shortener in Python: a small FastAPI service that turns a long URL into a short code, redirects visitors who open the code, and counts the clicks. Links are stored in a SQLite file, and custom aliases are supported. This is a fresh implementation built from `main`; it is an alternative to the standard-library version in #5, not a change to it.

## Flow

{{flow}}

## How to review

1. {{file:README.md}} — install, run and the API. Check that the three routes and the error statuses are what you want the service to expose.
2. {{file:shorty/store.py:46}} — `validate_url` and `validate_alias` decide what the service will redirect to and which names are allowed. Check that the rules are strict enough, and that not blocking private hosts is acceptable.
3. {{file:shorty/store.py:81}} — `LinkStore`: the table, code generation with retry, and click counting. Question whether a connection per operation suits how you plan to deploy it.
4. {{file:shorty/app.py:27}} — `create_app`: routes and status codes. Check `describe`, which builds the short URL from the request's address unless a base URL is set.
5. {{file:shorty/__main__.py:12}} — command-line options and defaults (binds to 127.0.0.1:8000, `links.db` in the working directory).
6. {{file:tests/test_shorty.py}} — API tests through FastAPI's test client. Check for cases you care about that are missing.

## Decisions

Each decision below is also an inline comment on the code it affected. Reply on the thread to discuss; run `/pr-kit:address-review` to pull replies back into the authoring session.

{{decisions}}

## Testing

`python -m pytest`: 24 tests pass on Python 3.12 (Windows). Shorten, redirect, stats and a rejected `javascript:` URL were also checked with curl against a running server. Nothing was tested under concurrent load or with multiple uvicorn workers.
