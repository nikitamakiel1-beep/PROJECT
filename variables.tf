variable "tenancy_ocid" {
  description = "OCI tenancy OCID supplied automatically by Resource Manager."
  type        = string
}

variable "compartment_ocid" {
  description = "Compartment where the free worker is created."
  type        = string
}

variable "region" {
  description = "OCI home region. Always Free resources must be created in the home region."
  type        = string
}

variable "instance_name" {
  description = "Display name for the worker VM."
  type        = string
  default     = "conway-replicatio-worker"

  validation {
    condition     = can(regex("^[A-Za-z][A-Za-z0-9-]{2,49}$", var.instance_name))
    error_message = "Use 3-50 letters, numbers, or hyphens, beginning with a letter."
  }
}

variable "availability_domain_index" {
  description = "Availability domain index. Change to 1 or 2 only when Oracle reports no A1 capacity."
  type        = number
  default     = 0

  validation {
    condition     = var.availability_domain_index >= 0 && var.availability_domain_index <= 2 && floor(var.availability_domain_index) == var.availability_domain_index
    error_message = "Availability domain index must be 0, 1, or 2."
  }
}

variable "ocpus" {
  description = "Ampere A1 OCPUs. The default uses the current Always Free total allocation."
  type        = number
  default     = 2

  validation {
    condition     = var.ocpus == 2
    error_message = "This browser-only free profile is fixed at 2 OCPUs."
  }
}

variable "memory_in_gbs" {
  description = "Ampere A1 memory. The default uses the current Always Free total allocation."
  type        = number
  default     = 12

  validation {
    condition     = var.memory_in_gbs == 12
    error_message = "This browser-only free profile is fixed at 12 GB."
  }
}

variable "boot_volume_size_in_gbs" {
  description = "Persistent boot disk for Docker images, Agent Wallet, SQLite, Ollama, and backups."
  type        = number
  default     = 100

  validation {
    condition     = var.boot_volume_size_in_gbs >= 50 && var.boot_volume_size_in_gbs <= 150
    error_message = "Choose 50-150 GB to remain safely inside the 200 GB Always Free storage pool."
  }
}
