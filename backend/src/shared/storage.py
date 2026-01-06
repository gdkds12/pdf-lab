from google.cloud import storage
import logging

logger = logging.getLogger(__name__)

class StorageClient:
    def __init__(self):
        self.client = storage.Client()
        
    def download_file(self, gcs_uri: str, destination_path: str):
        """Downloads a file from GCS to a local path."""
        if not gcs_uri.startswith("gs://"):
            raise ValueError("GCS URI must start with gs://")
            
        bucket_name, blob_name = gcs_uri[5:].split("/", 1)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        logger.info(f"Downloading {gcs_uri} to {destination_path}")
        blob.download_to_filename(destination_path)
        logger.info("Download completed.")

    def upload_file(self, local_path: str, gcs_uri: str):
        pass # Implement if needed
