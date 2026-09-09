# Creixement Cloud Runtime

Cloud-only execution plane for the Creixement autonomous company OS.

## Production root

Configure the Vercel project Root Directory as:

`cloud/creixement-runtime`

Do not deploy the repository root as the runtime project.

## Required server-side environment variables

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `CRON_SECRET`
- `CREIXEMENT_API_TOKEN`
- `CREIXEMENT_RUNTIME_ID` (optional, defaults in code)

All secret values stay in the deployment platform's server-side environment. Never place real values in GitHub, Lovable browser code, logs or generated reports.

## Endpoints

### `GET /api/tick`

Authenticated using `Authorization: Bearer $CRON_SECRET`. This is the only cron entry point. It:

1. discovers due enabled cron definitions from Supabase;
2. inserts idempotent `job_executions` records;
3. leases a bounded batch using `creixement_claim_jobs`;
4. checks global runtime controls;
5. reserves the live global resource budget;
6. checks required connector readiness;
7. runs only explicitly implemented safe handlers;
8. writes an execution receipt;
9. completes the leased job with an explicit succeeded/blocked/failed state.

The endpoint is fail-closed. Unknown handlers are blocked, not synthesized.

### `GET /api/health`

Authenticated using `Authorization: Bearer $CREIXEMENT_API_TOKEN`. Returns runtime/database reachability and the Chief Operator dashboard projection. It is not a public status page.

## Scheduler

`vercel.json` invokes `/api/tick` hourly. Supabase `job_definitions` remains the actual dynamic schedule catalogue; the hourly Vercel trigger simply wakes the scheduler. This keeps job cadence in governed database state instead of scattering cron rules across deployment configuration.

Because the wake-up interval is hourly, enabled database jobs that require sub-hour cadence must not be marked production-ready in this deployment profile. A higher-frequency scheduler can replace the wake-up layer later without changing the worker/job model.

## Safe initial handler set

The first runtime intentionally supports only receipt-producing internal handlers:

- `chief.compile_priorities`
- `automation.connector_health`
- `opportunity.refresh_radar`
- `evolution.evaluate_niches`
- `counterparty.refresh_staleness`
- `automation.dead_letter_triage`

Connector-dependent, external-message, public-publication, payment, contract, financing and property-commitment handlers remain blocked until their execution adapters and authorization envelopes are explicitly implemented and tested.

## Deployment gates

A deployment is not considered a production Creixement runtime merely because Vercel reports a successful build. Required verification includes:

- runtime package typecheck/tests green;
- migrations 002–008 present and upgrade path verified;
- `/api/health` authenticates and reaches Supabase;
- `/api/tick` authenticates using `CRON_SECRET`;
- one bounded internal job completes with an `execution_receipts` record;
- unknown/unimplemented handlers block safely;
- no required connector is shown runtime-ready without a real adapter;
- global budget enforcement is active;
- no unresolved critical incident blocks promotion;
- release manifest references the exact deployed commit and migration head.

## Production rule

No required local machine, Windows process, desktop Excel/COM instance, local scheduler, local filesystem or operator browser session may participate in production execution.