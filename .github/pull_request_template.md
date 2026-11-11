## Description
<!-- Provide a brief description of the changes introduced in this pull request. -->

## Changes Checklist
- [ ] Code follows repository style conventions (`ruff check` and `mypy` pass).
- [ ] Added or updated automated unit/contract tests for changed services.
- [ ] Verified that zero exchange API private keys, secrets, or real execution endpoints exist.
- [ ] No direct exchange connections or write calls in `dashboard/`.

## Documentation Checklist (Mandatory for Contract / Route changes)
- [ ] If contracts changed (`libs/contracts/events.py`), updated `docs/EVENTS.md` and registered event schemas.
- [ ] If FastAPI routes changed, regenerated `docs/openapi.json` and updated `docs/API.md`.
- [ ] If environment variables changed, documented defaults and behavior in `docs/OPERATIONS.md`.
- [ ] If architecture, ML logic, or risk rules changed, documented decisions in `docs/DECISIONS/` (ADR).
- [ ] Updated `docs/PROGRESS.md` with task details and status.
- [ ] Checked that all Mermaid diagrams in markdown render cleanly without syntax errors (`python scripts/verify_docs_ci.py`).
