# Creixement / Kairon V8 — Autonomy and Promotion Invariants

Kairon is the autonomous chief operator of Creixement. V8 separates maintenance autonomy from economic autonomy so runtime repair can remain available without silently granting commercial authority.

## Production identity

- Runtime: Cloudflare Workers
- Production branch: `production/creixement-kairon`
- State authority: Supabase/PostgreSQL
- Operator UI: Lovable
- Runtime version: `0.8.0`
- Migration head: `017_v8_release_attestation.sql`
- Target heartbeat: every five minutes

`main` is not a production branch for Kairon.

## Two autonomy planes

### Maintenance L2

Maintenance may run only while the global Creixement runtime control is active. It is limited to bounded reversible internal operations such as lease recovery, runtime reconciliation, connector health checks, dead-letter triage, bounded retry/backoff and circuit-breaker probes.

Maintenance must never relax policy, upgrade rights, enable payment authority, grant outbound authority or destroy governed evidence.

### Economic L2

Economic L2 is fail-closed. It requires all of the following at the same time:

1. Global runtime control active.
2. Exact deployed commit observed alive.
3. Exact production branch.
4. Verified green CI evidence for the exact commit.
5. Verified deployment evidence for the exact commit.
6. Verified migration head evidence.
7. Verified five-minute scheduler evidence and receipt.
8. Clean safety gate: no critical drift/incidents, job dead letters, outbox dead letters or open handler circuits.
9. Required providers operational, rights permitted and receipt-capable.
10. Budget and policy checks pass.

If any condition is false, Kairon may continue safe maintenance but economic L2 remains disabled.

## Owner-only boundary

Kairon never autonomously performs contracts/signatures, bank transfers or unrestricted payments, property offers/purchases, financing commitments, irreversible governed deletion, rights/consent bypass or unreceipted external action.

Outbound messaging, publication and public catalog mutation remain disabled until a separate versioned authorization envelope is approved.

## Evidence and truth

Release promotion is evidence-based rather than configuration-based. `release_evidence_v6` stores CI, deployment, migration, scheduler and manual-review evidence. `creixement_assess_release_v6` requires exact-commit evidence before setting `promotable=true`.

Truth precedence remains:

1. verified external outcome
2. executed connector receipt
3. governed source evidence
4. human-approved business decision
5. evidence-backed inference
6. hypothesis
7. generated narrative

Lower truth may not overwrite higher truth.

## Kairon cycle contract

`kairon_control_cycles_v7` is retained for compatibility, but V8 canonicalises its schema. `escalations` is an integer count and structured escalation data is stored in `escalation_details`. Completed cycle evidence is immutable. Every cycle carries correlation/idempotency identifiers, runtime identity, sensed state, priorities, automatic actions, blockers, outcome and evidence references.

`creixement_kairon_preflight_v8()` is the single database-level authority used by the runtime and cockpit to determine maintenance and economic L2 availability.

## Promotion flow

Development branches -> CI/audit -> `production/creixement-kairon` -> Cloudflare deployment -> heartbeat/scheduler/deployment evidence -> release attestation -> bounded economic L2.

A Git commit or successful build alone is never proof that production is running it.
