# Pre-client readiness and website construction

## Objective

Stage 003q completes every technical and operating component that can be completed before a real client exists. It does not create fictional clients, infer commercial traction or bypass provider, privacy, legal or human-release gates.

The target state is:

```text
source-ready
+ CRM architecture-ready
+ website construction-ready
+ service and delivery system-ready
= client-acquisition infrastructure ready

provider evidence
+ professional privacy/legal approval
+ publication QA
+ human release
= live intake ready
```

## Website construction

The release builder now materialises ten dedicated static routes from one versioned bilingual route contract:

1. `index.html`
2. `services.html`
3. `how-it-works.html`
4. `examples.html`
5. `about.html`
6. `insights.html`
7. `contact.html`
8. `privacy.html`
9. `cookies.html`
10. `legal.html`

Every secondary route is generated from `config/web-route-content.json`, which contains matched EN/ES content. The existing local multidimensional recommender, floating neural cards, light/dark themes, responsive layout and fictional demonstrations remain part of the main experience.

Source pages remain `noindex,nofollow`. A release artifact—not a source edit—controls whether a build becomes indexable.

## Release profiles

`build_web_release.py` supports three profiles.

### Preview

- blank endpoint;
- demonstration mode;
- synthetic-only;
- noindex;
- robots deny crawling;
- complete route and checksum artifact.

### Staging

- HTTPS endpoint required;
- synthetic-only;
- noindex;
- intended only for provider qualification and controlled test submissions;
- not a public client-acquisition site.

### Live

A live artifact is refused unless all eight activation gates are true:

- A01 provider suite 9/9;
- A02 idempotency;
- neural bridge evidence;
- cleanup evidence;
- professional privacy approval;
- professional legal/invoicing approval;
- website publication QA;
- named human live-release approval.

A successful live build changes the generated artifact to `index,follow`, writes permissive robots instructions, embeds the approved endpoint and records the activation-evidence digest. The source tree remains endpoint-free and noindex.

## CRM architecture

The canonical CRM contract now covers:

- Companies;
- Contacts;
- Leads;
- Opportunities;
- Activities;
- Services;
- Dashboard;
- Config;
- Automation Log;
- rebuildable Follow-up Digest;
- disposable Neural Shadow Queue.

The service vocabulary is:

- active principal: `IVA`, `CRM`, `IOP`;
- add-on: `WAB`;
- hidden until delivery evidence: `ISS`;
- legacy alias: `OSP → IOP`.

A CRM with headers and zero business rows is valid before clients exist. The readiness auditor must report zero pipeline, revenue and cash in that state. It must not add synthetic records merely to produce non-zero metrics.

## Readiness states

The auditor reports five distinct states.

### Source ready

All repository, website, CRM, templates, provider-source and rollback requirements exist and pass.

### Construction ready

A complete preview or staging artifact can be built from source without editing source files.

### Client-acquisition ready

The website experience, CRM architecture, service catalogue, qualification process, delivery masters and evidence system are ready to accept client activity once activation evidence is supplied.

### Live-intake ready

All provider, legal, privacy, publication and human-release gates are true.

### Paid-delivery ready

The legal identity, invoicing route, payment terms and human commercial release are approved.

The first three states do not require existing clients. The final two require external evidence and human decisions.

## Commands

```bash
python scripts/audit_pre_client_readiness.py
python scripts/test_pre_client_readiness.py
python scripts/build_web_release.py --profile preview --output dist/web-preview
```

A staging build requires an HTTPS endpoint. A live build additionally requires a complete activation-evidence JSON file.

## Current boundary

At source completion:

- client count may remain zero;
- CRM business rows may remain zero;
- no outreach is sent;
- no live endpoint is committed;
- no provider activation is claimed;
- no professional approval is inferred;
- no proposal, invoice, payment or delivery is claimed;
- Stage 003 remains active until the external activation gates pass.
