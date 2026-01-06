# Infrastructure Setup

This directory contains Terraform configuration to manage GCP resources.

## Prerequisites
- [Terraform](https://www.terraform.io/) installed
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated (`gcloud auth application-default login`)

## Steps
1. Create a `terraform.tfvars` file (do not commit this file if secrets are added, though here it's mainly Project ID):
   ```hcl
   project_id = "your-gcp-project-id"
   region     = "asia-northeast3" # Optional
   ```
2. Initialize Terraform:
   ```bash
   terraform init
   ```
3. Plan changes:
   ```bash
   terraform plan
   ```
4. Apply changes:
   ```bash
   terraform apply
   ```
