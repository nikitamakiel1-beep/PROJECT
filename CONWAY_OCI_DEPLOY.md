# Conway Replicatio — browser-only Oracle Always Free deployment

This deployment is deliberately **cloud-only**. Nothing in the normal path requires a local terminal, local Docker, local Node.js, local SQLite, SSH, WSL, PowerShell, or a locally running Conway process. SQLite, the Agent Wallet, models and runtime state live on the Oracle VM's persistent boot volume.

This branch contains public deployment documentation and bootstrap source only. The private Conway-Replicatio worker source remains in `nikitamakiel1-beep/Conway-Replicatio` and is accessed only after the owner enters a fine-grained GitHub read token into the HTTPS setup portal.

The current production deploy target is immutable OCI stack snapshot `6536ac96cb5bc714ff87733897519805b9504d0d`. That stack pins:

- Terraform OCI provider `8.23.0`;
- Terraform Random provider `3.9.0`;
- public host/bootstrap commit `f9f7134b70b79111ea58ce573556cf0ea18fd37a`;
- private Conway-Replicatio worker commit `2689083b93296523b81614b6768f6c5b5d95fa27`;
- Caddy `2.11.4-alpine`;
- Ollama `0.32.5`;
- original Conway Automaton `871c53e39b9180920c775759ddc38789699d69ea` inside the private worker build.

[![Deploy to Oracle Cloud](https://oci-resourcemanager-plugin.plugins.oci.oraclecloud.com/latest/deploy-to-oracle-cloud.svg)](https://cloud.oracle.com/resourcemanager/stacks/create?zipUrl=https://github.com/nikitamakiel1-beep/PROJECT/archive/6536ac96cb5bc714ff87733897519805b9504d0d.zip)

## Browser-only flow

1. Click **Deploy to Oracle Cloud**.
2. Sign in to Oracle Cloud and keep **Run apply** selected.
3. Use your tenancy home region and an Always Free-eligible compartment.
4. The immutable stack creates one `VM.Standard.A1.Flex` instance with 2 OCPUs, 12 GB RAM, a 100 GB boot volume, 4 GiB swap for one-time ARM build pressure, a VCN, public subnet, route, web-only security list and weekly boot-volume backup policy.
5. After Apply succeeds, open the `browser_setup_url` output and copy the `one_time_setup_code` output.
6. In that HTTPS portal enter:
   - the one-time setup code;
   - a fine-grained GitHub token owned by `nikitamakiel1-beep`, restricted to `Conway-Replicatio`, Contents read-only;
   - a public EVM Creator wallet address only.
7. Oracle verifies ownership, checks out the exact audited private worker commit, discards the GitHub token, builds the pinned Automaton + Replicatio image, downloads local `qwen3:4b`, generates the Agent Wallet and creates SQLite on Oracle persistent storage.
8. Before activation, Oracle automatically performs a real Ollama tool-call probe, writes a random persistence marker into SQLite, fingerprints the generated wallet file without exposing its key, restarts the worker container, waits for health, runs `PRAGMA integrity_check`, verifies the same SQLite marker and wallet fingerprint survived, and only then creates the pre-activation checkpoint.
9. Copy the generated Worker URL and Control Token into `https://conway-replicatio.lovable.app/setup` → **Connect Oracle worker**.
10. Click **I saved the control token — seal setup**. The setup portal stops revealing the token; a host timer disables the credential-entry service, removes its temporary credential files and prunes one-time Docker build cache.

## SQLite and persistence contract

SQLite is not local to the user's computer. The live database is `/opt/conway-replicatio/data/.automaton/state.db` on the Oracle boot volume and is mounted into the cloud worker as `/data/.automaton/state.db`.

The installer will not mark setup complete unless all of the following pass on Oracle:

- `state.db` exists on persistent storage;
- `wallet.json` exists on persistent storage;
- `PRAGMA integrity_check` returns `ok`;
- required Automaton tables are present, including `schema_version`, `identity`, `turns`, `kv` and `model_registry`;
- the SQLite schema version is valid;
- a cryptographically random persistence marker is committed to `kv`;
- a one-way SHA-256 fingerprint of the wallet file is stored in a local persistence receipt;
- the worker container is restarted;
- the same marker is still in SQLite after restart;
- the wallet fingerprint is unchanged after restart.

The resulting persistence receipt remains on the Oracle persistent volume. No private key, seed phrase or wallet password is exposed by the receipt.

A second systemd verifier is enabled for later Oracle VM boots. On every subsequent VM boot it re-opens the persisted SQLite database, re-runs `PRAGMA integrity_check`, verifies the persistence marker, verifies the wallet fingerprint and writes `boot-persistence-status.json` on the Oracle volume. A mismatch causes that verifier to fail rather than silently accepting changed state.

## First-boot security posture

- no public SSH rule;
- only TCP 80/443 are admitted by the OCI security list;
- worker 8080, internal supervisor 8081 and Ollama 11434 are rejected by the OCI security list and independently dropped for non-loopback traffic by the VM host firewall;
- the local-inference gateway prefers loopback binding when its Ollama backend is loopback;
- HTTPS uses Caddy with an IP-derived `sslip.io` hostname;
- private GitHub token is never stored in Terraform, cloud-init, `.env`, status files or logs;
- worker source is detached at an exact audited private commit rather than following a moving branch;
- worker control and Honey operator tokens are generated on the Oracle VM;
- Agent Wallet private key stays on Oracle persistent storage;
- local inference uses `qwen3:4b` through loopback HTTP only;
- both the original main inference registry and orchestration/provider registry are forced to local Ollama with no paid fallback;
- a real function/tool-call probe must pass before local inference is accepted;
- zero Conway Compute credits do not trigger critical/dead survival behavior in explicit zero-cost local mode;
- automatic Conway registration and bootstrap credit top-up are skipped in zero-cost local mode;
- max children = 0;
- child budget = 0;
- transfer/x402/inference spend limits = 0;
- Honey payouts disabled;
- checkpoint required before first activation;
- failed/retried browser installs preserve wallet/state and support controlled re-bootstrap rather than creating a new identity;
- watchdog limited to five agent restarts per ten-minute window;
- credential-entry service automatically disables after setup is sealed;
- one incremental OCI boot-volume backup is scheduled each Sunday at 03:00 UTC and retained for 28 days, using an explicit structured schedule.

## Persistence and recovery

The Agent Wallet, SQLite database, products, audit records and Automaton state all live on the Oracle boot volume. Container replacement does not intentionally delete them. The runtime creates a pre-activation integrity checkpoint and the installer independently proves persistence across a container restart before autonomous activation.

The OCI backup policy protects the complete boot volume independently from the containers. Backups are infrastructure-level crash-consistent backups, so the SQLite integrity/checkpoint checks remain relevant after restoration.

## Capacity note

Oracle may return `Out of host capacity` for Always Free Ampere A1. If that occurs, edit `availability_domain_number` and retry another availability domain where available, or retry later. The stack deliberately does not fall back to a paid shape.

## No secrets in Resource Manager variables

The Terraform stack contains no GitHub token, wallet private key, Conway key, control token or Honey token. The only generated Resource Manager credential is a temporary one-time setup code. It becomes unusable once setup is sealed and the setup service is disabled.

## Release gate

The software and infrastructure path is generated and statically hardened, but the first **real Oracle Resource Manager Apply** still requires the owner to authenticate to Oracle and authorize resource creation. After that single account-boundary action, the cloud installer performs the ARM build, local model setup, wallet creation, SQLite initialization, SQLite integrity proof, persistence restart test, checkpoint and worker start automatically.

No Agent Wallet funding should happen before that live Oracle Apply completes successfully and the Lovable dashboard reports a healthy connected worker.
