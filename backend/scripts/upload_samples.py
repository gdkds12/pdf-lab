from google.cloud import storage
import os
import sys

# Add backend to path to load config if needed, but we can just use the bucket name directly
# or try to load from env.
from dotenv import load_dotenv
load_dotenv("backend/.env")

# Hardcoded fallback from setup_test_data.py if env is missing
BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "project-thunder-assets-pdf-lab-468815")

def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_name)
        print(f"File {source_file_name} uploaded to gs://{bucket_name}/{destination_blob_name}")
        return f"gs://{bucket_name}/{destination_blob_name}"
    except Exception as e:
        print(f"Failed to upload {source_file_name}: {e}")
        return None

if __name__ == "__main__":
    print(f"Target Bucket: {BUCKET_NAME}")
    
    # Upload PDF
    pdf_path = "backend/sample.pdf"
    if os.path.exists(pdf_path):
        upload_blob(BUCKET_NAME, pdf_path, "sample.pdf")
    else:
        print(f"{pdf_path} not found.")

    # Upload Audio
    audio_path = "backend/sample.wav"
    if os.path.exists(audio_path):
        upload_blob(BUCKET_NAME, audio_path, "sample.wav")
    else:
        print(f"{audio_path} not found.")
