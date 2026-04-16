# SCHEMA BATCH LOG

Purpose: track user-facing schema batches separately from code-only refactor work.

## Batch policy
- schema changes should be batched, not dripped out piecemeal
- each batch must have explicit scope and downstream notes
- if a change is not required for the current checkpoint, defer it

## Batch A
Reserved for the first narrow additive read-performance index release.

Record here:
- included changes
- explicitly excluded changes
- verification notes
- release-note text
- rollback notes

## Future schema candidates
Use this section to list deferred changes such as:
- search columns
- helper tables
- later index batches
- obsolete-table removal batches if separated
