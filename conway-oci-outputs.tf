output "worker_public_ip" {
  description = "Public IPv4 address of the Oracle worker."
  value       = oci_core_instance.replicatio.public_ip
}

output "worker_hostname" {
  description = "Automatic TLS hostname backed by sslip.io."
  value       = local.worker_hostname
}

output "browser_setup_url" {
  description = "Open this URL in your browser after cloud-init finishes. No SSH or local terminal is required."
  value       = "https://${local.worker_hostname}/setup/"
}

output "one_time_setup_code" {
  description = "Temporary code for the browser setup portal. It is sealed after you acknowledge the generated control token."
  value       = random_password.setup_code.result
  sensitive   = true
}

output "lovable_worker_url" {
  description = "Worker URL to enter in Conway Replicatio on Lovable after browser setup completes."
  value       = "https://${local.worker_hostname}"
}

output "backup_policy" {
  description = "Automatic persistent-state protection applied to the Oracle boot volume."
  value       = "Incremental every Sunday at 03:00 UTC, retained 28 days (normally four scheduled backups, leaving one of the five Always Free backup slots available)."
}

output "deployment_safety" {
  description = "First-boot safety posture."
  value       = "2 OCPU / 12 GB Ampere A1, 100 GB persistent boot volume, ports 80+443 only, no SSH ingress, local qwen3:4b inference, maxChildren=0, external spending=0, Honey payouts disabled, pre-activation checkpoint, weekly OCI boot-volume backups, and browser setup portal auto-disabled after sealing."
}
