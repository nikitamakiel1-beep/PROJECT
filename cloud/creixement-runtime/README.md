# Creixement Cloud Runtime v6.1

This package is the cloud-only execution fabric for the Creixement venture factory. It is intentionally fail-closed: source code or a configured connector is not treated as proof of deployment, health, authorization or external effect.

## Deployment root

Deploy this directory as the project root:

`cloud/creixement-runtime`

The production runtime requires the server-only variables listed in `.env.example`. Never expose `SUPABASE_SERVICE_ROLE_KEY`, `CRON_SECRET`, `CREIXEMENT_API_TOKEN` or `CREIXEMENT_OWNER_TOKEN` to browser code.

## Endpoints

- `GET|POST /api/tick` — scheduler-authenticated runtime iteration. Bearer `CRON_SECRET`.
- `GET /api/health` — authenticated dependency health. Bearer `CREIXEMENT_API_TOKEN`.
- `GET /api/readiness` — authenticated machine readiness and blocker report. Bearer `CREIXEMENT_API_TOKEN`.
- `GET|POST /api/owner-decisions` — owner decision queue/ingress. Bearer `CREIXEMENT_OWNER_TOKEN`. Recording a decision is never itself consequential execution.
- `GET|POST /api/release-status` — release attestation/readiness. Bearer `CREIXEMENT_API_TOKEN`.

## Runtime iteration

Every tick executes independent phases:

1. expired lease recovery;
2. event-outbox routing;
3. idempotent cron scheduling with a bounded 25-hour recovery window;
4. desired-state reconciliation with drift history preservation;
5. governed job claiming/execution.

Job execution requires runtime controls, a closed/eligible circuit breaker, budget reservation, connector readiness, a known safe handler, idempotency and an execution receipt. Unknown handlers remain blocked.

## Scheduling

The repository's Vercel configuration contains one daily safety wake-up compatible with the currently connected Hobby plan. It is not evidence of continuous autonomy.

Production continuous autonomy requires an independently verified scheduler binding at five-minute cadence or better in `scheduler_bindings_v6`. The `/api/tick` endpoint is provider-neutral and can be called by a managed cloud scheduler using `Authorization: Bearer <CRON_SECRET>`.

The runtime uses a 1500-minute bounded recovery lookback. It schedules only the latest applicable occurrence for each cron job and relies on idempotency keys to prevent duplicate execution.

## Database migration order

Apply in order through:

`012_v6_resilience_and_release_integrity.sql`

Migration 012 adds crash recovery for expired job/outbox leases, concurrency-aware job claiming, single-probe half-open circuits, immutable/conflict-safe owner decisions, preserved drift history and stricter release promotion gates.

## Production gate

`v_production_gate_v6` is the concise machine gate. A release is not promotable unless all of the following are true at assessment time:

- CI succeeded;
- a healthy runtime heartbeat exists;
- a verified high-frequency scheduler exists;
- enabled job connector dependencies are runtime-ready;
- critical drift and critical incidents are zero;
- open job/outbox dead letters are zero;
- open handler circuits are zero.

External outreach, publication, payments, contracts and property commitments remain disabled until separately governed authorization envelopes and production connectors are explicitly approved and verified.

## Verification sequence

After deployment:

1. call `/api/health` with the operator token;
2. call `/api/tick` with the scheduler secret;
3. confirm a fresh row in `runtime_heartbeats_v5`;
4. confirm `/api/readiness` reports the actual blockers rather than optimistic defaults;
5. activate and verify the five-minute scheduler binding;
6. run `/api/release-status` assessment with the exact deployed commit SHA and green CI evidence;
7. promote only when `v_production_gate_v6.promotable = true`.

A green GitHub workflow alone is not production readiness, and a deployed function alone is not continuous autonomy.
