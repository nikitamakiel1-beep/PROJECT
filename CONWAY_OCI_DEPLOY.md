# Conway Replicatio — browser-only Oracle Always Free deployment

This branch contains a public Terraform bootstrap package only. The private Conway-Replicatio worker source remains in `nikitamakiel1-beep/Conway-Replicatio` and is cloned once after the owner enters a fine-grained GitHub read token into the HTTPS setup portal.

[![Deploy to Oracle Cloud](https://oci-resourcemanager-plugin.plugins.oci.oraclecloud.com/latest/deploy-to-oracle-cloud.svg)](https://cloud.oracle.com/resourcemanager/stacks/create?zipUrl=https://github.com/nikitamakiel1-beep/PROJECT/archive/refs/heads/conway-oci-stack.zip)

## Browser-only flow

1. Click **Deploy to Oracle Cloud**.
2. Sign in to Oracle Cloud and keep **Run apply** selected.
3. Use your tenancy home region and an Always Free-eligible compartment.
4. The stack creates one `VM.Standard.A1.Flex` instance with 2 OCPUs, 12 GB RAM and a 100 GB boot volume, plus a VCN, public subnet, route and web-only security list.
5. After Apply succeeds, open the `browser_setup_url` output and copy the `one_time_setup_code` output.
6. In that HTTPS portal enter:
   - the one-time setup code;
   - a fine-grained GitHub token owned by `nikitamakiel1-beep`, restricted to `Conway-Replicatio`, Contents read-only;
   - a public EVM Creator wallet address only.
7. The portal verifies ownership, clones the private branch, discards the GitHub token, builds the pinned Automaton + Replicatio Docker image, downloads local `qwen3:4b`, generates the Agent Wallet, applies zero-spend/zero-child policy, creates the pre-activation checkpoint and starts the worker under the watchdog.
8. Copy the generated Worker URL and Control Token into `https://conway-replicatio.lovable.app/setup` → **Connect an existing worker**.
9. Click **I saved the control token — seal setup**. The setup portal will no longer reveal the token.

## First-boot security posture

- no public SSH rule;
- only TCP 80/443 are admitted by the OCI security list;
- worker 8080, internal supervisor 8081 and Ollama 11434 are not admitted publicly;
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
- the watchdog is rate-limited to five agent restarts per ten-minute window.

## Capacity note

Oracle may return `Out of host capacity` for Always Free Ampere A1. If that occurs, edit `availability_domain_number` and retry another availability domain where available, or retry later. The stack deliberately does not fall back to a paid shape.

## No secrets in Resource Manager variables

The Terraform stack contains no GitHub token, wallet private key, Conway key, control token or Honey token. The only generated Resource Manager credential is a temporary one-time setup code; it is invalidated when the owner seals the browser setup portal.
