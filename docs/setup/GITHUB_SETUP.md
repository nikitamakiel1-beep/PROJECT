# GitHub setup

## Repository settings

- Visibility: private
- Default branch: `main`
- Issues: enabled
- Actions: enabled
- Merge method: squash preferred
- Delete head branches after merge: enabled

## Branch protection after the bootstrap commit

Protect `main` with:

- pull request required,
- at least one approval when another reviewer is available,
- required status checks: `repository-validation` and `handoff-validation`,
- conversation resolution required,
- force pushes and branch deletion disabled.

## Optional secrets

The base repository works without external secrets. Add these only when their related integration is activated:

- `LINEAR_API_KEY`
- `OPENAI_API_KEY`
- deployment-provider secrets

## Optional variables

- `LINEAR_TEAM_ID`
- `LINEAR_PROJECT_ID`
- `PUBLIC_SITE_URL`

Do not activate an autonomous AI workflow until spending limits, permitted file paths and human approval gates are defined.
