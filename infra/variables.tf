variable "project_id" {
  description = "The GCP Project ID"
  type        = string
}

variable "region" {
  description = "The default GCP region for resources"
  type        = string
  default     = "asia-northeast3" # Seoul region
}

variable "bucket_name_prefix" {
  description = "Prefix for GCS buckets"
  type        = string
  default     = "project-thunder"
}
