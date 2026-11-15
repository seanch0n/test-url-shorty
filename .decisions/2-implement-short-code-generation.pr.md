## Summary

Adds the service that picks short codes for new links (#2). Generated codes are random 7-character Base62 strings; collisions are checked before saving and retried up to 5 times. User-supplied aliases go through a separate validation path. Stacked on #14 (the storage layer), so this diff shows only the code generation.

## Flow

{{flow}}

## How to review

1. {{file:shorty/codes.py:34}} — `generate_code`. Check it uses `secrets`, not `random`, and that 7 characters is long enough for you.
2. {{file:shorty/codes.py:81}} — the retry loop. Check that both the pre-check and the caught `DuplicateShortCodeError` lead to a retry, and that it stops after `max_attempts`.
3. {{file:shorty/codes.py:41}} — alias validation and the reserved list above it. Question whether the allowed characters and reserved names are right.
4. {{file:shorty/codes.py:74}} — a taken alias is an error, never retried or altered.
5. {{file:tests/test_codes.py:1}} — scripted generators force collisions and an insert race deterministically.

## Decisions

Each decision below is also an inline comment on the code it affected. Reply on the thread to discuss; run `/pr-kit:address-review` to pull replies back into the authoring session.

{{decisions}}

## Testing

`python -m pytest -q`: 34 passed (12 storage + 22 code generation). Collision and race handling are tested with injected generators, not real random collisions.
