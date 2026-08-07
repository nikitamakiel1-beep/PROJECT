# Conway Replicatio — browser-only Oracle Always Free deployment

This branch contains a public Terraform bootstrap package only. The private Conway-Replicatio worker source remains in `nikitamakiel1-beep/Conway-Replicatio` and is cloned once after the owner enters a fine-grained GitHub read token into the HTTPS setup portal.

[![Deploy to Oracle Cloud](https://oci-resourcemanager-plugin.plugins.oci.oraclecloud.com/latest/deploy-to-oracle-cloud.svg)](https://cloud.oracle.com/resourcemanager/stacks/create?zipUrl=https://github.com/nikitamakiel1-beep/PROJECT/archive/refs/heads/conway-oci-stack.zip)

## Browser-only flow

1. Click **Deploy to Oracle Cloud**.
2. Sign in to Oracle Cloud and keep **Run apply** selected.
3. Use your tenancy home region and an Always Free-eligible compartment.
4. The stack creates one `VM.Standard.A1.Flex` instance with 2 OCPUs, 12 GB RAM and a 100 GB boot volume, plus a VCN, public subnet, route, web-only security list and weekly boot-volume backup policy.
5. After Apply succeeds, open the `browser_setup_url` output and copy the `one_time_setup_code` output.
6. In that HTTPS portal enter:
   - the one-time setup code;
   - a fine-grained GitHub token owned by `nikitamakiel1-beep`, restricted to `Conway-Replicatio`, Contents read-only;
   - a public EVM Creator wallet address only.
7. The portal verifies ownership, clones the private branch, discards the GitHub token, builds the pinned Automaton + Replicatio Docker image, downloads local `qwen3:4b`, generates the Agent Wallet, applies zero-spend/zero-child policy, creates the pre-activation checkpoint and starts the worker under the watchdog.
8. Copy the generated Worker URL and Control Token into `https://conway-replicatio.lovable.app/setup` → **Connect Oracle worker**.
9. Click **I saved the control token — seal setup**. The setup portal stops revealing the token, and a host-side timer then disables the browser setup service completely.

## First-boot security posture

- no public SSH rule;
- only TCP 80/443 are admitted by the OCI security list;
- worker 8080, internal supervisor 8081 and Ollama 11434 are rejected by the OCI security list and independently dropped for non-loopback traffic by the VM host firewall;
- the local-inference gateway also prefers loopback binding when its Ollama backend is loopback;
- HTTPS uses Caddy with an IP-derived `sslip.io` hostname;
- private GitHub token is never stored in Terraform, cloud-init, `.env`, status files or logs;
- worker control and Honey operator tokens are generated on the Oracle VM;
- Agent Wallet private key stays in `/opt/conway-replicatio/data/.automaton` on the Oracle boot volume;
- local inference uses `qwen3:4b` through loopback HTTP only;
- paid baseline inference models are disabled in the local-only configuration;
- max children = 0;
- child budget = 0;
- transfer/x402/inference spend limits = 0;
- Honey payouts disabled;
- a checkpoint is required before first activation;
- the watchdog is rate-limited to five agent restarts per ten-minute window;
- the browser credential-entry service is automatically disabled after the owner seals setup;
- the boot volume receives one incremental OCI backup each Sunday at 03:00 UTC, retained for 28 days. This normally keeps four scheduled backups and leaves one of Oracle Always Free's five total volume-backup slots available for an owner-initiated emergency backup.

## Persistence and recovery

The Agent Wallet, SQLite database, products, audit records and Automaton state live on the Oracle boot volume. Docker/container replacement does not intentionally delete them. The runtime also creates a pre-activation integrity checkpoint before it is allowed to start autonomously.

The OCI backup policy protects the entire boot volume independently of the running containers. A backup remains a crash-consistent infrastructure backup rather than an application-level transaction snapshot, so the SQLite integrity/checkpoint gate remains relevant after any restore.

## Capacity note

Oracle may return `Out of host capacity` for Always Free Ampere A1. If that occurs, edit `availability_domain_number` and retry another availability domain where available, or retry later. The stack deliberately does not fall back to a paid shape.

Oracle documents 2 OCPUs / 12 GB total Ampere A1 capacity, 200 GB combined Always Free boot/block storage, and up to five Always Free volume backups in the tenancy home region. The stack uses 100 GB of that storage and intentionally limits its scheduled backup retention to stay within the five-backup ceiling under normal operation.

## No secrets in Resource Manager variables

The Terraform stack contains no GitHub token, wallet private key, Conway key, control token or Honey token. The only generated Resource Manager credential is a temporary one-time setup code. It becomes invalid when the owner seals the browser setup portal, after which the portal service is disabled.
