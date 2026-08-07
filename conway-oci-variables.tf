variable "tenancy_ocid" {
  type        = string
  description = "OCI tenancy OCID, automatically provided by Resource Manager."
}

variable "compartment_ocid" {
  type        = string
  description = "Compartment in which the free worker resources will be created."
}

variable "region" {
  type        = string
  description = "OCI region. Always Free compute must be used in your tenancy home region."
}

variable "availability_domain_number" {
  type        = number
  description = "Availability domain number. Use 1 in single-AD regions such as eu-madrid-3."
  default     = 1

  validation {
    condition     = var.availability_domain_number >= 1 && var.availability_domain_number <= 3 && floor(var.availability_domain_number) == var.availability_domain_number
    error_message = "availability_domain_number must be 1, 2, or 3."
  }
}

variable "compute_profile" {
  type        = string
  description = "Always Free Ampere A1 size. full uses 2 OCPU/12 GB; compact uses 1 OCPU/6 GB and can improve placement odds when the region is capacity-constrained."
  default     = "full"

  validation {
    condition     = contains(["full", "compact"], var.compute_profile)
    error_message = "compute_profile must be full or compact."
  }
}

variable "instance_display_name" {
  type        = string
  description = "Display name for the free Oracle worker VM."
  default     = "conway-replicatio-worker"

  validation {
    condition     = length(var.instance_display_name) >= 3 && length(var.instance_display_name) <= 64
    error_message = "instance_display_name must contain 3-64 characters."
  }
}

variable "bootstrap_ref" {
  type        = string
  description = "Pinned public bootstrap source ref. Do not change unless intentionally upgrading the installer."
  default     = "f9f7134b70b79111ea58ce573556cf0ea18fd37a"
}
