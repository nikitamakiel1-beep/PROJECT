# Synthetic Real-Estate Synergy Orchestrator

**Stage:** 008r  
**Automation:** A25  
**Status:** Executable synthetic fixture only.

## Purpose

Stage 008r turns the Stage 007r contracts into an executable, fail-closed orchestration layer without introducing a real CRM, Google Drive, email, messaging or payment client.

It reuses A30 for:

- governed property normalization;
- traditional, room and temporary scenario generation;
- monthly-loan underwriting metrics;
- one-mandate/one-scenario fit scoring;
- no-write CRM merge planning.

It does not create a second formula engine.

## Supported event paths

### Property case

A synthetic source row passes through rights validation, restricted-field scanning and A30 normalization. The output is a deterministic mutation plan for:

- Properties;
- Property Scenarios;
- RE Import Staging.

The plan is applied only to an in-memory fixture.

### Visit and evidence

The runtime accepts synthetic visit metadata and restricted synthetic evidence pointers. Media with unverified rights or non-synthetic pointers is quarantined.

### Report generation and approval

A generated report remains `not_shareable`. Approval requires four approved roles—financial, evidence, legal and commercial—with four distinct synthetic reviewer tokens. Approval changes only the internal share state to `approved`; it does not send or publish the report.

### Pairwise match proposal

The runtime evaluates one supplied mandate against supplied A30 scenarios. Results remain `review_required`, `human_approved=false`, and cannot create a commercial Opportunity or external communication.

## Event controls

Every event requires:

- synthetic event ID;
- synthetic idempotency key;
- correlation ID;
- canonical payload digest;
- supported event type;
- explicit synthetic payload flag.

A repeated event with the same key and payload returns a replay receipt without adding rows. A repeated key with a different payload is quarantined.

## Restricted-data controls

The runtime rejects raw email, phone, address, cadastral reference, listing URL, client/investor names, source notes and HTTP URLs. Only `restricted://synthetic/...` pointers are accepted in the fixture.

## Runtime boundary

The module imports no network, Google API, spreadsheet, mail or messaging library. All receipts state:

```json
{
  "real_writes_permitted": false,
  "external_communication_permitted": false,
  "transaction_action_permitted": false
}
```

## Validation

`python scripts/test_real_estate_synergy_orchestrator.py` covers deterministic property/scenario plans, idempotent replay, conflicting replay, rights quarantine, restricted URL quarantine, pairwise matching, visit evidence, report approval separation and absence of network clients.
