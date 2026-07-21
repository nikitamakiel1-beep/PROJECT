# A01 synthetic intake-to-CRM mapping

This mapping is authoritative for Stage 002. The live CRM headers were read from the Google Sheets file on 21 July 2026 and stored in `schemas/crm/sheets-contract.json`.

## Payload mapping

| Website payload | CRM destination | Rule |
|---|---|---|
| `submission_id` | Leads → Notes; Activities → Source / Link; Automation Log → Trigger Record | Idempotency and correlation key. Never displayed as contact data. |
| `company_name` | Companies → Company Name; Leads → Company | Trimmed. Existing company rows are never overwritten. |
| `contact_name` | Contacts → Full Name; Leads → Contact Name | Trimmed. Existing contact rows are never overwritten. |
| `email` | Contacts → Email; Leads → Email | Lower-cased deterministic contact key. |
| `website` | Companies → Website and Source URLs; Leads → Website | Host is normalised for company matching. |
| `country` | Companies → Country; Leads → Country | Optional. |
| `phone` | Contacts → Phone; Leads → Phone | Optional and absent from the current public form. |
| `role` | Contacts → Role; Leads → Role | Optional and absent from the current public form. |
| `service_code` | Leads → Service Interest | Must be one of the active canonical codes in `schemas/services.json`. |
| `problem` | Leads → Notes | Maximum 3,000 characters. No copy is written to Automation Log. |
| `consent_version` | Contacts → Notes; Leads → Consent Basis | Must exactly equal the deployed Script Property. |
| `preferred_language` | Companies → Languages; Contacts → Language | `en`, `es`, `ca` or `other`. |
| `source` | Leads → Source | Defaults to `Website assessment`. |
| `submitted_at` | Created Date, Date and Consent Date fields | Valid ISO timestamp or server timestamp fallback. |

## Deterministic matching

1. Contact is matched by normalised email.
2. An existing contact's current Company ID takes precedence. The intake never moves a curated contact to another company.
3. When there is no existing contact, company is matched by normalised website host; without a website, by normalised company name.
4. New company and contact identifiers are deterministic hashes of the matching key.
5. Lead and intake-activity identifiers are deterministic hashes of `submission_id`.
6. A successful Automation Log entry for the same `submission_id` turns later attempts into `duplicate` results with no operational writes.
7. Partial rows from an interrupted historical attempt are reused by deterministic identifiers; missing rows are created without duplicating existing ones.

## Human-data preservation

The public intake is create-only for Companies and Contacts. It does not replace names, roles, sectors, notes, owners, relationship strength or other manually curated fields. Conflicting company data attached to an existing email is logged as a warning, not applied.

## Transaction and recovery model

The Apps Script acquires a script lock, validates every sheet header, reads a snapshot and calculates a complete write plan before mutation. Appended rows are tracked. Any write failure deletes the appended rows in reverse order. A minimal `failed` Automation Log row is then attempted outside the rolled-back transaction.

Google Sheets does not provide multi-sheet database transactions. Deterministic identifiers, locking, append tracking and reverse deletion are the compensating controls.
