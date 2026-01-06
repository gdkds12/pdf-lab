# Enable necessary APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "storage-component.googleapis.com",
    "firebase.googleapis.com"
  ])
  service = each.key
  disable_on_destroy = false
}

# Artifact Registry for Docker Images
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "thunder-backend-repo"
  description   = "Docker repository for Project Thunder Backend"
  format        = "DOCKER"

  depends_on = [google_project_service.apis]
}

# GCS Buckets
resource "google_storage_bucket" "assets" {
  name          = "${var.bucket_name_prefix}-assets-${var.project_id}"
  location      = var.region
  force_destroy = false # Prevent accidental deletion

  uniform_bucket_level_access = true

  depends_on = [google_project_service.apis]
}

# Cloud Run Job Definition
resource "google_cloud_run_v2_job" "default" {
  name     = "thunder-worker"
  location = var.region

  template {
    template {
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}/worker:latest"
        resources {
          limits = {
            cpu    = "2"
            memory = "4Gi"
          }
        }
        env {
            name = "GCP_PROJECT"
            value = var.project_id
        }
        env {
            name = "GCP_LOCATION"
            value = var.region
        }
        env {
            name = "SUPABASE_URL"
            value = var.supabase_url
        }
        env {
            name = "SUPABASE_KEY"
            value = var.supabase_key
        }
        env {
            name = "GCS_BUCKET_NAME"
            value = google_storage_bucket.assets.name
        }
        env {
            name = "INGEST_BATCH_PAGES"
            value = "20"
        }
        env {
            name = "EMBED_BATCH_SIZE"
            value = "8"
        }
      }
    }
  }

  depends_on = [google_project_service.apis] 
}
