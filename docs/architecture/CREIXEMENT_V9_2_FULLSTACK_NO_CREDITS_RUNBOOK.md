# Creixement / Kairon V9.2 — Fullstack No-Credits Runbook

Canonical staging branch: `venture/creixement-kairon-v9-fullstack-no-credits`

Production target branch: `production/creixement-kairon`

Runtime version: `0.9.2`

Migration head: `021_v9_runtime_proof_and_scheduler_autoverify.sql`

## Operating architecture

- GitHub is code, CI and release truth.
- Supabase PostgreSQL is canonical durable state and control-plane truth.
- Cloudflare Workers is the primary production runtime and five-minute scheduler.
- The repository-root React/Vite application is the credits-free operator cockpit.
- Lovable is optional/private UI tooling. It is not a runtime dependency and its credit state must never block Creixement operation.
- Configuration is never evidence of execution. Runtime execution is proven by persisted heartbeats and receipts.

## V9.2 runtime proof contract

`runtime_heartbeats_v5` remains the low-cardinality current-state register.

`runtime_heartbeat_samples_v9` is append-only execution evidence. Every call to `creixement_record_heartbeat_v5` appends an immutable sample while updating the current-state register.

A Cloudflare scheduler is considered verified only when all of the following are true:

1. Runtime ID is `kairon-cloudflare-v9`.
2. Samples are healthy `tick_completed` heartbeats.
3. Samples refer to the same deployed commit SHA.
4. At least three completed healthy samples exist in the 30-minute proof window.
5. The maximum observed gap is at most eight minutes for the five-minute contract.
6. The latest completed sample is still fresh.

`creixement_auto_verify_cloudflare_scheduler_v9()` promotes `cloudflare-primary-heartbeat` to active only after those conditions are independently observed. The trigger on `runtime_heartbeat_samples_v9` performs this automatically after each completed healthy Cloudflare tick.

## Credits-free UI

The repository root is a standalone Vite/React cockpit. It can be developed, built and deployed without Lovable build credits.

Required browser environment values:

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_PUBLISHABLE_KEY`

Optional browser value:

- `VITE_KAIRON_RUNTIME_URL` — public Worker origin used only for safe `/diagz` and `/healthz` diagnostics.

Never expose any of the following to browser code:

- `SUPABASE_SERVICE_ROLE_KEY`
- `CRON_SECRET`
- `CREIXEMENT_API_TOKEN`
- `CREIXEMENT_OWNER_TOKEN`

The cockpit fails closed when live data is unavailable and distinguishes verified runtime evidence from configured state.

## Cloudflare production configuration

Worker source directory:

`cloud/creixement-cloudflare-runtime`

Public versioned variables are already defined in `wrangler.toml`, including the Supabase project URL, runtime ID and runtime version.

Minimum secret required for autonomous scheduled execution:

- `SUPABASE_SERVICE_ROLE_KEY`

Additional secrets required only for authenticated HTTP control or owner-decision endpoints:

- `CRON_SECRET`
- `CREIXEMENT_API_TOKEN`
- `CREIXEMENT_OWNER_TOKEN`

Use `npm run deploy:ci` in Cloudflare CI whenever possible. It refuses a CI deployment without a commit SHA and injects `CREIXEMENT_COMMIT_SHA` plus the deployed branch into the Worker runtime. A production deployment must be traceable to the exact green GitHub SHA.

## Promotion procedure

1. Keep all work on the dedicated staging branch until both GitHub workflows are green.
2. Verify migration 021 exists live in Supabase.
3. Open a PR from the dedicated branch to `production/creixement-kairon`.
4. Merge only after all intended changes are in that PR and all required checks are green.
5. Deploy Cloudflare from the fully merged production SHA, never from an unmerged or partial branch.
6. Observe at least three healthy completed five-minute ticks.
7. Confirm `v_runtime_proof_summary_v9.cloudflare_scheduler_verified=true` and `v_runtime_cadence_proof_v9.cadence_stable=true`.
8. Assess the release gate only after CI evidence, matching deployed commit heartbeat, scheduler proof and safety checks all converge.

## Owner-only / account-level actions

These cannot be completed from repository code alone:

- Setting Cloudflare account secrets and authorizing the first production deployment.
- OAuth or consent grants for Google, Gmail, Calendar, Contacts and other external providers.
- Changing GitHub repository visibility.
- Defining/approving any L3 outbound authority envelope.

## Constitutional boundary

Kairon can autonomously observe, research, recommend and perform bounded reversible internal operations up to L2 under policy. Payments, contracts, financing commitments, property commitments, external publication/outreach outside an approved envelope, source-rights bypass and irreversible governed deletion remain L3 and fail closed.

## Release truth checklist

A release is not production-ready merely because it builds. Production truth requires:

- Core CI green.
- UI CI green.
- Required migration live.
- Exact deployed commit known.
- Healthy runtime heartbeat matching that commit.
- Stable scheduler cadence proven by immutable samples.
- No critical runtime drift/incidents/dead letters/open circuits.
- Required provider dependencies runtime-ready and permitted.

If any item is unknown, the truthful state is `blocked`, `needs_setup` or `unavailable`, never success.
