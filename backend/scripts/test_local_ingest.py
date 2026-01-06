import os
import uuid
import logging
from src.shared.db import get_supabase_client
from src.shared.storage import StorageClient
from src.shared.config import Config
from src.phase1.ingest_pipeline import IngestPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_test_data():
    """
    1. Uploads sample.pdf to GCS
    2. Creates a record in 'sources' table (and subjects)
    3. Returns source_id and gcs_url
    """
    supabase = get_supabase_client()
    storage = StorageClient()
    
    # 1. Upload sample PDF
    local_path = "sample-image.pdf"
    if not os.path.exists(local_path):
        logger.error(f"Sample file {local_path} not found. Please place a PDF file named 'sample-image.pdf' in backend/ root.")
        return None, None
        
    bucket_name = Config.GCS_BUCKET_NAME
    if not bucket_name:
        logger.error("GCS_BUCKET_NAME not set in .env")
        return None, None

    blob_name = f"test-ingest/{uuid.uuid4()}.pdf"
    gcs_url = f"gs://{bucket_name}/{blob_name}"
    
    logger.info(f"Uploading {local_path} to {gcs_url}...")
    storage.upload_file(local_path, gcs_url)
    
    # 2. Setup DB Records
    user_id = str(uuid.uuid4()) # Dummy
    subject_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    
    # Create Subject
    subject_data = {
        "subject_id": subject_id,
        "user_id": user_id,
        "name": "Local Ingest Test Subject"
    }
    logger.info(f"Creating subject record: {subject_id}")
    try:
        supabase.table("subjects").insert(subject_data).execute()
    except Exception as e:
        logger.error(f"Failed to insert subject: {e}")
        return None, None
    
    # Create Source
    source_data = {
        "source_id": source_id,
        "user_id": user_id, 
        "subject_id": subject_id,
        "title": "Local Ingest Test PDF",
        "gcs_pdf_url": gcs_url,
        "ingest_status": "queued",
        "kind": "textbook"
    }
    
    logger.info(f"Creating source record: {source_id}")
    try:
        supabase.table("sources").insert(source_data).execute()
    except Exception as e:
        logger.error(f"Failed to insert source: {e}")
        return None, None
        
    return source_id, gcs_url

def verify_result(source_id):
    supabase = get_supabase_client()
    
    # Check Source Status
    res = supabase.table("sources").select("*").eq("source_id", source_id).execute()
    if not res.data:
        logger.error("Source not found after ingest.")
        return
        
    source = res.data[0]
    logger.info(f"Source Status: {source['ingest_status']}")
    logger.info(f"Page Count: {source.get('page_count')}")
    
    # Check Chunks
    res = supabase.table("chunks").select("*").eq("source_id", source_id).execute()
    chunks = res.data
    logger.info(f"Generated Chunks: {len(chunks)}")
    if chunks:
        logger.info(f"Sample Chunk 1: {chunks[0]['content_text'][:50]}...")
        logger.info(f"Embedding Length: {len(chunks[0]['embedding']) if chunks[0].get('embedding') else 'None'}")
    else:
        logger.warning("No chunks found. Something might be wrong.")

def main():
    logger.info("Starting End-to-End Ingest Test...")
    
    source_id, gcs_url = setup_test_data()
    if not source_id:
        logger.error("Setup failed. Aborting.")
        return
        
    logger.info("Running Pipeline...")
    try:
        pipeline = IngestPipeline(source_id, gcs_url)
        pipeline.run()
        
        logger.info("Pipeline Finished. Verifying...")
        verify_result(source_id)
        
    except Exception as e:
        logger.error(f"Test Failed with Exception: {e}", exc_info=True)

if __name__ == "__main__":
    main()
