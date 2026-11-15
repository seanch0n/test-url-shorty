## Summary

Adds the URL shortener this repo is for: a small Python service that turns a long URL into a short code, redirects visitors who open the code, and counts the clicks. It uses only the standard library and stores links in a SQLite file, so it runs with `python -m shortener` and nothing to install. Custom aliases and a simple web form are included.

## Flow

{{flow}}

## How to review

1. {{file:README.md}} — how to run it and the API. Check that the three routes and the error statuses are what you want the service to expose.
2. {{file:shortener/store.py:47}} — `validate_url` decides what the service is willing to redirect to. Check that the rules are strict enough (http/https only, no control characters) and not too strict (non-ASCII hostnames are rejected).
3. {{file:shortener/store.py:87}} — `LinkStore`: the table, code generation with collision retry, and click counting. Question whether one shared connection behind a lock is enough for how you plan to deploy it.
4. {{file:shortener/server.py:65}} — `ShortenerHandler`: routing, body limits and status codes. Check `_describe`, which builds the short URL from the Host header unless `--base-url` is set.
5. {{file:shortener/__main__.py:7}} — command-line options and defaults (binds to 127.0.0.1:8000, `links.db` in the working directory).
6. {{file:tests/test_shortener.py}} — store tests and end-to-end HTTP tests. Check for cases you care about that are missing.

## Decisions

Each decision below is also an inline comment on the code it affected. Reply on the thread to discuss; run `/pr-kit:address-review` to pull replies back into the authoring session.

{{decisions}}

## Testing

`python -m unittest discover -s tests`: 14 tests pass on Python 3.12 (Windows), including requests against a live server on a local port. The web form's JavaScript was not exercised in a browser, and nothing was tested under concurrent load.
