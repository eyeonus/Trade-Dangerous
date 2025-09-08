# Archive

This folder contains **legacy and dormant modules** from the Trade Dangerous
codebase. They are **not used in current workflows** and are **not maintained**,
but are retained for reference and historical context.

## Purpose

- Preserve code that was once part of Trade Dangerous, but is now obsolete or
  superseded.
- Document features that illustrate the project’s evolution (e.g. pre-API OCR
  workflows, deprecated export formats).
- Provide a starting point if anyone wishes to revisit or revive old ideas.

## Current Contents

- **update_gui.py**  
  Text-based GUI for manual entry of station prices, dating back to the
  *OCR era* (before FDev API or EDDN). Used to generate `.prices` files for
  upload to Maddavo’s site. Purely historical.

- **jsonprices.py**  
  Deprecated JSON exporter, retained for backward reference. Emits a warning
  when run.

- **mapping.py / edapi_plug.py**  
  Experimental modules for direct API ingestion. Left here as a reference point
  but non-functional against the current FDev API.

- **journal_plug.py / netlog_plug.py**  
  Early attempts at importing player logs. Never widely adopted; superseded by
  community tools.

## Policy

- **Do not refactor**: These files are frozen in their legacy form.
- **Do not import**: No active commands or plugins depend on them.
- **Safe to delete**: If space or clarity is critical, this directory can be
  removed without affecting supported features.

---

*Trade Dangerous development focus is on the maintained commands and plugins in
`tradedangerous/`. Everything here is purely archival.*
