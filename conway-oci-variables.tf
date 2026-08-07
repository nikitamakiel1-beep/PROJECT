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
  description = "Availability domain number to try for Ampere A1 capacity. Change and re-apply if Oracle reports out-of-host-capacity."
  default     = 1

  validation {
    condition     = var.availability_domain_number >= 1 && var.availability_domain_number <= 3 && floor(var.availability_domain_number) == var.availability_domain_number
    error_message = "availability_domain_number must be 1, 2, or 3."
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
  default     = "564a64bda67aa1fa31cdffdc0a1e893ead430c93"
}
