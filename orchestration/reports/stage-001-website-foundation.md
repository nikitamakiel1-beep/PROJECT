# Stage 001 report — website and public-offer foundation

## Outcome

Converted the original static foundation into a credible bilingual validation alpha while keeping real lead collection disabled. The site now presents the three active services from one canonical source, explains who the offers do and do not fit, includes three clearly labelled demonstration previews, and provides an accessible local-only assessment experience.

The work also removed the duplicated browser service catalogue. The website now reads `schemas/services.json` directly when the repository root is served, making that file the only authoritative source for public prices, scope, delivery windows, ideal-fit statements, deliverables and revision limits.

## Files changed

- Rebuilt `apps/web/index.html` with stronger semantic structure, responsive navigation, explicit alpha status, fit boundaries, demonstration coverage and accessible form help.
- Rebuilt `apps/web/assets/styles.css` with mobile navigation, improved contrast, responsive layouts, focus states, status states and reduced-motion handling.
- Rebuilt `apps/web/assets/app.js` with data-contract checks, DOM-safe rendering, bilingual metadata, accessible theme/menu state, local validation, honeypot protection, request timeout and explicit success/failure handling.
- Expanded `apps/web/assets/translations.json` with equivalent English and Spanish keys.
- Added `apps/web/assets/demonstrations.json` for three non-client demonstration previews.
- Expanded `schemas/services.json` with bilingual ideal-fit statements, deliverables and one bounded revision.
- Removed `apps/web/assets/services.json`, which had duplicated the canonical catalogue.
- Kept `apps/web/config.js` in demonstration mode and documented the Stage 002 gate.
- Added `scripts/test_web.py` and strengthened `scripts/validate_repository.py`.
- Updated `.github/workflows/ci.yml`, `README.md` and `MANIFEST.json` in the complete validated package.

## Tests and evidence

The following checks passed locally:

```bash
python scripts/validate_repository.py
python scripts/test_web.py
node --check apps/web/assets/app.js
python scripts/orchestrator.py validate
```

`test_web.py` verifies translation-key parity, HTML anchor integrity, the exact active-service set, canonical service-catalogue use, demonstration coverage, demo-mode enforcement and a static HTTP smoke test for the page and required JSON/JavaScript resources.

The website was served from the repository root and all tested resources returned HTTP 200. The form remains unable to send data because `demoMode` is true and `intakeEndpoint` is blank.

## Business or operational effect

A prospect can now understand the current service boundary, compare deliverables and prices, see what is explicitly excluded and test the assessment experience without unknowingly transmitting personal information. The site avoids invented social proof and states that demonstrations are not client work.

The stronger service data model also gives Stage 002 a stable contract for mapping `service_code` into the CRM without copying names or prices into the website code.

## Risks and unresolved items

- The website is intentionally `noindex` and not production deployed.
- Real intake remains blocked until the Apps Script endpoint is tested with synthetic data, duplicate handling is verified and the privacy/commercial gate is approved.
- Static hosting must expose both `apps/web` and `schemas`; a later deployment stage may need a build step that copies the canonical catalogue into the deployable artifact while preserving one source of truth.
- The demonstration previews describe structure but do not yet include downloadable example documents.

## Rollback

Restore the Stage 000 package or revert all Stage 001 files. Keep `apps/web/config.js` in `demoMode: true`; do not restore the removed duplicate service catalogue unless a controlled build process generates it from `schemas/services.json` and validates exact parity.

## Next instruction

`orchestration/instructions/stage-002-synthetic-intake-crm-contract.md`
