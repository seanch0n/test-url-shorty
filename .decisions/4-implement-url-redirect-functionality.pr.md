## Summary

Adds `GET /<short_code>` (#4), the redirect that makes short links work. Known codes get a 302 to the destination exactly as stored, unknown codes get a 404, and disabled or expired links get a 410. Each redirect is one indexed read with no writes and is marked uncacheable, so disabling a link takes effect at once. Stacked on #16; also adds run and configuration notes to the README.

## Flow

{{flow}}

## How to review

1. {{file:shorty/app.py:97}} — `follow_link`, the whole redirect path. Check the order of the checks and the status codes.
2. {{file:shorty/app.py:100}} — the regex fast-path. Check it can never reject a code that could have been stored (it reuses the alias pattern, which is a superset of Base62).
3. {{file:shorty/app.py:112}} — the `Location` header. Check that `iri_to_uri` leaves existing escapes alone.
4. {{file:shorty/app.py:114}} — `no-store`. Decide whether you'd rather trade a little caching for slower disable/expiry.
5. {{file:tests/test_redirect.py:1}} — preservation cases, 404/410 handling, and a SQL trace that asserts one SELECT per redirect.
6. {{file:README.md:1}} — run instructions and environment variables.

## Decisions

Each decision below is also an inline comment on the code it affected. Reply on the thread to discuss; run `/pr-kit:address-review` to pull replies back into the authoring session.

{{decisions}}

## Testing

`python -m pytest -q`: 86 passed, 16 of them redirect tests. Also smoke-tested with `flask run` and curl: create, 302 redirect with path and query intact, `ftp://` rejected, unknown code 404. No load testing.
