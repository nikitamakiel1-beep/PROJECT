locals {
  shape             = "VM.Standard.A1.Flex"
  ad_count          = length(data.oci_identity_availability_domains.ads.availability_domains)
  selected_ad_index = min(var.availability_domain_index, max(local.ad_count - 1, 0))
  selected_ad       = data.oci_identity_availability_domains.ads.availability_domains[local.selected_ad_index].name
  raw_base_url      = "https://raw.githubusercontent.com/nikitamakiel1-beep/PROJECT/conway-oci-deploy-v1"
  bronze_policy_ids = [for policy in data.oci_core_volume_backup_policies.oracle.volume_backup_policies : policy.id if lower(policy.display_name) == "bronze"]
  common_tags = {
    application = "Conway-Replicatio"
    deployment  = "browser-only-always-free"
    managed-by  = "OCI-Resource-Manager"
  }
}

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

data "oci_core_volume_backup_policies" "oracle" {}

data "oci_core_images" "ubuntu" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = local.shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "random_password" "bootstrap_token" {
  length  = 48
  special = false
}

resource "oci_core_vcn" "worker" {
  compartment_id = var.compartment_ocid
  cidr_blocks     = ["10.42.0.0/16"]
  display_name    = "${var.instance_name}-vcn"
  dns_label       = "replicatio"
  freeform_tags   = local.common_tags
}

resource "oci_core_internet_gateway" "worker" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.worker.id
  display_name   = "${var.instance_name}-internet-gateway"
  enabled        = true
  freeform_tags  = local.common_tags
}

resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.worker.id
  display_name   = "${var.instance_name}-public-routes"
  freeform_tags  = local.common_tags

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.worker.id
  }
}

resource "oci_core_security_list" "public_https" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.worker.id
  display_name   = "${var.instance_name}-https-only"
  freeform_tags  = local.common_tags

  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    description = "HTTP for automatic HTTPS certificate issuance"

    tcp_options {
      min = 80
      max = 80
    }
  }

  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    description = "HTTPS control and bootstrap portal"

    tcp_options {
      min = 443
      max = 443
    }
  }

  ingress_security_rules {
    protocol = "1"
    source   = "0.0.0.0/0"
    description = "ICMP path MTU discovery"

    icmp_options {
      type = 3
      code = 4
    }
  }

  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
    description = "Required for package, GitHub, model, and certificate downloads"
  }
}

resource "oci_core_subnet" "public" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.worker.id
  cidr_block                 = "10.42.1.0/24"
  display_name               = "${var.instance_name}-public-subnet"
  dns_label                  = "worker"
  route_table_id             = oci_core_route_table.public.id
  security_list_ids          = [oci_core_security_list.public_https.id]
  prohibit_public_ip_on_vnic = false
  freeform_tags              = local.common_tags
}

resource "oci_core_instance" "worker" {
  availability_domain = local.selected_ad
  compartment_id      = var.compartment_ocid
  display_name        = var.instance_name
  shape               = local.shape
  freeform_tags       = local.common_tags

  shape_config {
    ocpus         = var.ocpus
    memory_in_gbs = var.memory_in_gbs
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.public.id
    assign_public_ip = true
    display_name     = "${var.instance_name}-primary-vnic"
    hostname_label   = "conway"
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu.images[0].id
    boot_volume_size_in_gbs = var.boot_volume_size_in_gbs
    boot_volume_vpus_per_gb = 10
  }

  instance_options {
    are_legacy_imds_endpoints_disabled = true
  }

  metadata = {
    user_data = base64encode(templatefile("${path.module}/cloud-init.yaml.tftpl", {
      bootstrap_token = random_password.bootstrap_token.result
      raw_base_url    = local.raw_base_url
    }))
  }

  lifecycle {
    precondition {
      condition     = length(data.oci_core_images.ubuntu.images) > 0
      error_message = "No Canonical Ubuntu 24.04 ARM image was found in this region."
    }
  }
}

resource "oci_core_volume_backup_policy_assignment" "bronze" {
  count = length(local.bronze_policy_ids) > 0 ? 1 : 0

  asset_id  = oci_core_instance.worker.boot_volume_id
  policy_id = local.bronze_policy_ids[0]
}
