# Preview and provider bundles

This branch adds reproducible artifacts without advancing the recursive stage pointer. Stage 003 remains blocked until the real disposable Apps Script provider test passes.

## Website preview

Build a self-contained demonstration-only website:

```bash
python scripts/build_preview.py
python -m http.server 8080 --directory dist/web-preview
```

Open `http://localhost:8080`.

The builder:

- copies the website into `dist/web-preview`;
- copies the canonical service catalogue into the preview root;
- rewrites only the copied service-data path;
- refuses to build unless `demoMode: true` and the intake endpoint is blank;
- produces `PREVIEW_BUILD.json` and `SHA256SUMS`.

No live endpoint or operational identifier is added.

## Apps Script provider bundle

Create the deterministic installation ZIP:

```bash
python scripts/package_apps_script.py
```

Outputs:

- `dist/apps-script/`
- `dist/stage-003-apps-script.zip`

The ZIP contains only synthetic-safe source, the Apps Script manifest and deployment instructions. Script Properties, spreadsheet IDs and deployment URLs remain outside GitHub.

## Provider evidence compiler

After `runProviderHttpSuite()` finishes, copy the returned JSON object into a local file that is not committed, for example `provider-result.local.json`.

```bash
python scripts/generate_provider_evidence.py \
  --input provider-result.local.json \
  --output orchestration/evidence/stage-003-provider-runtime.md
```

The compiler refuses to produce a report unless:

- `synthetic_only` is true;
- the complete expected case sequence is present;
- every case passed;
- the overall provider suite passed;
- cleanup passed and restored the starting row counts.

The generated Markdown omits submission IDs, names, emails, spreadsheet IDs, deployment URLs and response payload details that are not needed for the decision.

## Public-repository safety

Until `PROJECT` becomes private, run:

```bash
python scripts/check_public_safety.py
```

The check rejects committed spreadsheet URLs, Apps Script deployment URLs, assigned provider IDs, common API keys, GitHub tokens and private keys.

## GitHub Actions artifacts

The `tooling-artifacts` workflow builds and uploads:

1. the demonstration website preview;
2. the synthetic Apps Script provider bundle.

Artifacts are execution aids, not production deployments. Public intake remains disabled until a later explicit activation gate.
