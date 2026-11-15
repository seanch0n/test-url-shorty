## Summary

First piece of the Python URL shortener: the storage layer the code generator (#2), create endpoint (#3) and redirect (#4) will build on. It adds a SQLite schema applied through numbered SQL migrations, a `LinkRepository` for creating and looking up links, and env-var configuration. No new runtime dependencies.

## Flow

{{flow}}

## How to review

1. {{file:shorty/migrations/0001_create_links.sql:1}} — the `links` table and the unique index on `short_code`. Check the columns cover what #3 and #4 need (expiry, disabled flag).
2. {{file:shorty/db.py:22}} — the migration runner. Check that each migration is atomic and re-running is a no-op.
3. {{file:shorty/repository.py:65}} — `LinkRepository.create` and the duplicate translation. Question whether matching SQLite's error text is acceptable.
4. {{file:shorty/repository.py:41}} — `is_expired` / `is_usable`, and `list_unusable` below. Check the UTC-text timestamp comparison.
5. {{file:shorty/config.py:15}} — `SHORTY_DATABASE_PATH` and `SHORTY_DATABASE_TIMEOUT`.
6. {{file:tests/test_persistence.py:1}} — one test per acceptance criterion, plus a query-plan check that lookups use the index.

## Decisions

Each decision below is also an inline comment on the code it affected. Reply on the thread to discuss; run `/pr-kit:address-review` to pull replies back into the authoring session.

{{decisions}}

## Testing

`python -m pytest -q`: 11 passed (Python 3.12, SQLite via stdlib). Not tested against concurrent writers.
