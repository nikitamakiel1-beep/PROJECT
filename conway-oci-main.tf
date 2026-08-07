terraform {
  required_version = ">= 1.5.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 6.0.0, < 8.0.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6.0, < 4.0.0"
    }
  }
}

provider "oci" {
  region = var.region
}

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

data "oci_core_images" "ubuntu" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = "VM.Standard.A1.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "random_password" "setup_code" {
  length  = 24
  special = false
}

resource "oci_core_vcn" "replicatio" {
  compartment_id = var.compartment_ocid
  cidr_block     = "10.77.0.0/16"
  display_name   = "conway-replicatio-vcn"
  dns_label      = "replicatio"
}

resource "oci_core_internet_gateway" "replicatio" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.replicatio.id
  display_name   = "conway-replicatio-internet"
  enabled        = true
}

resource "oci_core_route_table" "replicatio" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.replicatio.id
  display_name   = "conway-replicatio-routes"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.replicatio.id
  }
}

resource "oci_core_security_list" "replicatio" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.replicatio.id
  display_name   = "conway-replicatio-web-only"

  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 80
      max = 80
    }
    description = "HTTP for automatic TLS certificate issuance"
  }

  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 443
      max = 443
    }
    description = "HTTPS browser setup and Replicatio control gateway"
  }
}

resource "oci_core_subnet" "replicatio" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.replicatio.id
  cidr_block                 = "10.77.1.0/24"
  display_name               = "conway-replicatio-public-subnet"
  dns_label                  = "worker"
  prohibit_public_ip_on_vnic = false
  route_table_id             = oci_core_route_table.replicatio.id
  security_list_ids          = [oci_core_security_list.replicatio.id]
}

resource "oci_core_instance" "replicatio" {
  compartment_id      = var.compartment_ocid
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[var.availability_domain_number - 1].name
  display_name        = var.instance_display_name
  shape               = "VM.Standard.A1.Flex"
  preserve_boot_volume = false

  shape_config {
    ocpus         = 2
    memory_in_gbs = 12
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.replicatio.id
    assign_public_ip = true
    display_name     = "conway-replicatio-primary-vnic"
    hostname_label   = "replicatio"
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu.images[0].id
    boot_volume_size_in_gbs = 100
    boot_volume_vpus_per_gb = 10
  }

  metadata = {
    user_data = base64encode(templatefile("${path.module}/cloud-init.yaml.tftpl", {
      setup_code    = random_password.setup_code.result
      bootstrap_ref = var.bootstrap_ref
    }))
  }

  freeform_tags = {
    "ConwayReplicatio" = "browser-only-free-worker"
    "SafetyMode"       = "zero-spend-zero-child-first-boot"
  }
}

locals {
  worker_hostname = "${replace(oci_core_instance.replicatio.public_ip, ".", "-")}.sslip.io"
}
