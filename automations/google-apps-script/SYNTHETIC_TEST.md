# Disposable-sheet synthetic test procedure

Use the fictional domain `example.test`. Never enter real names, addresses or telephone numbers.

| Case | Expected Companies | Contacts | Leads | Activities | Log result |
|---|---:|---:|---:|---:|---|
| New submission | +1 | +1 | +1 | +1 | accepted |
| Exact retry | +0 | +0 | +0 | +0 | duplicate |
| Existing company / new contact | +0 | +1 | +1 | +1 | accepted |
| Existing contact | +0 | +0 | +1 | +1 | accepted |
| Malformed email | +0 | +0 | +0 | +0 | rejected |
| Missing company | +0 | +0 | +0 | +0 | rejected |
| Invalid service | +0 | +0 | +0 | +0 | rejected |
| Injected write failure | +0 after rollback | +0 | +0 | +0 | failed |

For each request, record only:

- submission ID;
- correlation ID;
- result;
- deterministic company/contact/lead/activity IDs;
- before and after row counts;
- retry count;
- rollback outcome.

Do not copy the request body or synthetic contact fields into the stage report.
