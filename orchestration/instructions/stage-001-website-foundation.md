# Stage 001 instruction — website and public-offer foundation

## Objective

Turn the static website foundation into a credible alpha that accurately presents the three active services and routes assessment requests into a test endpoint without collecting real prospect data prematurely.

## Read first

- `README.md`
- `docs/architecture/SYSTEM_OF_RECORD.md`
- `docs/architecture/AUTOMATION_BOUNDARIES.md`
- `orchestration/reports/stage-000-bootstrap.md`
- `schemas/services.json`

## Work

1. Review all EN/ES website content for parity, factual restraint and clarity.
2. Ensure service cards render exclusively from `schemas/services.json` or an equivalent single canonical source.
3. Improve accessibility, responsive behaviour, theme switching and navigation.
4. Add a clearly labelled demonstration section without fabricated clients or testimonials.
5. Keep the form in demonstration mode unless an explicitly configured endpoint exists.
6. Add lightweight local validation and a success/failure state.
7. Add or improve repository tests needed for these changes.

## Acceptance criteria

- All public links and controls work.
- EN and ES contain equivalent information.
- Service prices and scope are consistent everywhere.
- No client claims or invented metrics appear.
- The form does not silently discard submissions.
- The website works from a simple static server.
- `python scripts/validate_repository.py` passes.

## Exclusions

- No real lead acquisition.
- No paid advertising.
- No production deployment.
- No analytics or non-essential cookies.
- No expansion beyond the current service menu.

## Required handoff

Create:

1. `orchestration/reports/stage-001-website-foundation.md`
2. `orchestration/instructions/stage-002-<evidence-based-slug>.md`
3. Updated `orchestration/state.json`
4. Updated `orchestration/CURRENT.md`

The stage-002 instruction must be derived from actual stage-001 results. It should normally address intake-to-CRM integration, but must change if validation reveals a more urgent blocker.
