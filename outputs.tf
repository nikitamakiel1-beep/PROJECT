output "deployment_status" {
  description = "The VM exists. Cloud-init then installs the protected bootstrap portal; allow 5-12 minutes before opening it."
  value       = "OCI infrastructure created. Wait for the bootstrap portal to become available."
}

output "public_ip" {
  description = "Public IPv4 address of the worker."
  value       = oci_core_instance.worker.public_ip
}

output "worker_url" {
  description = "Final HTTPS worker URL. It becomes operational after browser bootstrap finishes."
  value       = "https://${oci_core_instance.worker.public_ip}.sslip.io"
}

output "bootstrap_url" {
  description = "Open this protected browser URL after apply. The fragment token is not sent in HTTP requests."
  value       = "https://${oci_core_instance.worker.public_ip}.sslip.io/bootstrap/#token=${random_password.bootstrap_token.result}"
  sensitive   = true
}

output "next_step" {
  description = "Browser-only next step."
  value       = "Reveal the sensitive bootstrap_url output, open it, and complete the protected web installer. Never share that URL."
}

output "automatic_boot_volume_backup" {
  description = "Whether Oracle's Bronze scheduled backup policy was found and attached."
  value       = length(oci_core_volume_backup_policy_assignment.bronze) == 1 ? "Enabled (Oracle Bronze policy)" : "Not attached; verify backup policy manually before funding."
}
