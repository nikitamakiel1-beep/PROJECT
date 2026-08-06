# Security model

## Never enter

The deployment never needs a seed phrase, private key, wallet password, exchange recovery code, primary personal wallet secret, Oracle API key, or Conway website password.

## Secrets used

- Terraform-generated bootstrap token: protects the temporary web installer.
- GitHub fine-grained token: read-only clone of one private repository, then overwritten and deleted.
- Worker control token: authorises Lovable-to-worker API calls.
- Honey operator token: remains server-only; Honey is disabled in the initial profile.

## Network exposure

Only TCP 80 and 443 are permitted by the generated OCI security list. Caddy redirects/protects HTTPS. Internal worker, supervisor, Ollama, and compatibility ports remain on loopback or the private Docker network.

## Standalone compatibility service

This deployment does not impersonate a funded Conway account. The local service exists only so the pinned Automaton can run its original loop with local execution and local inference. It reports a virtual health balance to avoid an artificial survival shutdown and denies cloud/payment mutations. The UI and audit record label the mode `standalone-local-free`.

## Failure policy

- incomplete installation: worker is stopped;
- missing checkpoint: activation blocked;
- five child-process restarts within ten minutes: emergency lockdown;
- portal seal: web copy of the control token is deleted and the installer service stops;
- database integrity failure: installation aborts.
