# Deterministic lead ordering across page boundaries

## Context

PR #71 snapshots legacy leads in 500-row pages before committing the completed
migration. Both native lead stores ordered only by descending score; equal
scores lacked a unique order, which can duplicate or omit leads at page
boundaries on PostgreSQL. Existing migration fixtures assigned distinct scores.

## Decision

Order page queries by score descending and then lead ID ascending in both the
ORM and SQLite stores. Keep the complete migration in one transaction and
explicitly document its intentional lock-duration tradeoff. Cover tied scores
in the public migration route and execute page queries in both native stores.

## Alternatives

Deduplicating migration rows and refusing to commit an incomplete unique set
would detect some failures, but would leave ordinary workbook paging ambiguous.
Keyset paging could avoid OFFSET costs but changes the public paging contract.

## Consequences

Equal-score pages have a defined unique order. Existing score priority is
preserved. This does not provide a snapshot against concurrent source mutations;
that is a separate isolation concern. Large migrations still hold one write
transaction until their complete snapshot and marker can commit atomically.

## Validation

Python 3.12.3 with the repository's frozen uv dependencies: the new native-store
regressions failed on the reviewed head in both backends (2 failed, 12 passed),
then 20 tests passed after the change. Checks cover 501 tied native-store leads,
public migrations at 0/2/500/501/1001 rows with distinct and equal scores,
rollback on unavailable later pages, and existing lead-list paging. The ORM
implementation was executed on SQLite; a live PostgreSQL server was not used.
`git diff --check` passed. Logs remain local in the parent evidence directory.
