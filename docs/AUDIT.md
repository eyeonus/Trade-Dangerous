# AUDIT

Purpose: classify suspiciously ancient or potentially dead code paths.

## Classification legend
- Core live
- Compatibility live
- Dead
- Unknown — needs runtime tracing

## Entry-point inventory
Record supported live entry points here:
- CLI
- GUI
- packaged bootstrap path
- plugin/import paths

## Candidate inventory
For each candidate, record:
- path or module
- why it looks suspicious
- evidence of reachability or non-reachability
- classification
- proposed checkpoint for action
- risk note

## Deletion policy
Prefer quarantine then delete.
Do not delete anything user-visible until reachability has been checked.
