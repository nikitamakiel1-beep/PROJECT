# Automation boundaries

## Automate

- Validation and normalisation
- Duplicate checks
- Record creation
- Folder creation
- Internal reminders and reports
- Template population
- Quality-control checks

## Human approval required

- External sales messages
- Proposals and pricing exceptions
- Contracts and invoices
- Legal or funding interpretations
- Final client deliverables
- Destructive data changes

## Engineering requirements

Every automation must be idempotent, logged, least-privilege, retry-safe and capable of manual recovery.
