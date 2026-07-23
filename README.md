# International Growth Venture

Versioned operating infrastructure for a zero-capital, validation-stage international-growth service venture.

## Active offer boundary

Only three principal services are public at launch:

1. International Visibility Audit — €149
2. CRM & Lead Tracker Setup — €299
3. International Sales One-Pager — €249

WhatsApp Business Setup remains an add-on. The International Starter System remains hidden until standalone delivery evidence exists.

## Systems of record

- **GitHub:** website, schemas, automation code, templates and stage handoffs.
- **Google Drive:** CRM, operational records, client data and deliverables.
- **Linear:** execution, dependencies, dates, blockers and decision gates.

Do not commit CRM exports, client records, credentials or private research.

## Run the website alpha

The website reads the canonical service catalogue from `schemas/services.json`, so serve the repository root:

```bash
python -m http.server 8080
```

Then open:

```text
http://localhost:8080/apps/web/
```

The validation alpha is `noindex` and remains in demonstration mode. The form validates locally but does not transmit or retain entries.

## Validate the repository

```bash
python scripts/validate_repository.py
python scripts/test_web.py
python scripts/test_intake_contract.py
node --check apps/web/assets/app.js
python scripts/orchestrator.py validate
```

## Recursive execution

Read `orchestration/CURRENT.md`, the active instruction and the previous report before changing source. Every stage must produce a report and a bounded instruction for the next sequential stage.

```bash
python scripts/orchestrator.py show
```

Advance only after the current implementation, tests, report and next instruction are complete:

```bash
python scripts/orchestrator.py complete \
  --stage N \
  --report orchestration/reports/stage-NNN-description.md \
  --next-instruction orchestration/instructions/stage-NEXT-description.md
```

See `docs/architecture/RECURSIVE_EXECUTION.md` for stop conditions and human approval boundaries.

## Synthetic intake contract

Stage 002 provides a pure Apps Script-compatible intake core, an exact Google Sheets header contract and a nine-case local harness. The public website remains in demonstration mode. Provider deployment and any endpoint are controlled by Stage 003 and must never be committed.
