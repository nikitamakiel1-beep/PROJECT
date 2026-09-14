# Lovable branch — Kairon V9

Canonical UI branch: `lovable/creixement-kairon-v9`.

Purpose: Lovable should consume this branch through GitHub two-way sync. Lovable is not the code-generation authority for this branch; GitHub is. External commits are expected to be pulled into the Lovable editor/preview.

Do not point the Lovable project at `main` or `production/creixement-kairon`.

Runtime separation:
- `lovable/creixement-kairon-v9`: operator cockpit / UI.
- `venture/creixement-kairon-v9-bioecology`: Kairon/runtime development.
- `production/creixement-kairon`: Cloudflare production runtime.

The UI uses only browser-safe Supabase variables (`VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` or `VITE_SUPABASE_ANON_KEY`). Server/service-role credentials and Creixement owner/cron/API tokens must never be committed or exposed to the browser.

UI surfaces include Kairon, Overview, recommendations, opportunities, approvals, products, CRM, reports, revenue, Tectum, agents, runs, automations, experiments, ecology V9, lineages, niches, adversarial courts, immune memory, canaries, connectors, policies, audit and health/release state.
