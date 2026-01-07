import json
import logging
import math
import subprocess
import concurrent.futures
import google.auth
from typing import List, Dict, Any
from google.cloud import storage
from datetime import timedelta

from src.shared.config import Config
from src.shared.db import get_supabase_client
from src.phase2 import signal_extraction  # Import directly

logger = logging.getLogger(__name__)

# Constants
CHUNK_DURATION_SEC = 1800  # 30 minutes

def run(payload_str: str):
    logger.info("Phase 2 Dispatcher: Splitting Audio Started (Single Worker Mode)")
    
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON payload")

    session_id = payload.get("session_id")
    gcs_audio_url = payload.get("gcs_audio_url")
    subject = payload.get("subject", "Unknown")
    exam_window = payload.get("exam_window", "midterm")

    if not all([session_id, gcs_audio_url]):
        raise ValueError("Missing session_id or gcs_audio_url")

    # 1. Get Audio Duration
    duration_sec = get_audio_duration(gcs_audio_url)
    logger.info(f"Total Duration: {duration_sec} seconds ({timedelta(seconds=duration_sec)})")

    # 2. Calculate Chunks
    num_chunks = math.ceil(duration_sec / CHUNK_DURATION_SEC)
    if num_chunks == 0: num_chunks = 1 # minimal safeguard
    
    logger.info(f"Splitting into {num_chunks} chunks of ~{CHUNK_DURATION_SEC} sec")

    # 3. Create Chunk Records in DB
    supabase = get_supabase_client()
    chunks_to_process = []
    
    for i in range(num_chunks):
        start = i * CHUNK_DURATION_SEC
        end = min((i + 1) * CHUNK_DURATION_SEC, duration_sec)
        dur = end - start
        
        # We don't necessarily need audio_chunks table for this mode if we process on fly,
        # but tracking status is good. For now, create them.
        chunks_to_process.append({
            "session_id": session_id,
            "chunk_index": i,
            "gcs_chunk_url": gcs_audio_url, 
            "start_offset_sec": start,
            "duration_sec": dur,
            "status": "pending" # Initial status
        })
    
    result = supabase.table("audio_chunks").insert(chunks_to_process).execute()
    created_chunks = result.data
    
    # 4. Update Session Status
    supabase.table("sessions").update({"status": "extracting"}).eq("session_id", session_id).execute()

    # 5. Process all chunks locally in parallel (ThreadPool)
    # Using 'copy' codec in ffmpeg makes this very lightweight on CPU.
    # Parallelism constrained by Network Bandwidth & Memory, not CPU.
    process_chunks_locally(created_chunks, subject, exam_window)

    # 6. Mark Session Complete
    supabase.table("sessions").update({"status": "reasoning"}).eq("session_id", session_id).execute()
    logger.info("Phase 2 Dispatcher: All chunks processed successfully.")


def get_audio_duration(gcs_uri: str) -> float:
    storage_client = storage.Client(project=Config.GCP_PROJECT)
    bucket_name = gcs_uri.replace("gs://", "").split("/")[0]
    blob_name = "/".join(gcs_uri.replace("gs://", "").split("/")[1:])
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # Check for service account credentials to handle signing in Cloud Run
    credentials, _ = google.auth.default()
    sa_email = getattr(credentials, "service_account_email", None)

    if sa_email:
        signed_url = blob.generate_signed_url(expiration=timedelta(minutes=5), service_account_email=sa_email)
    else:
        signed_url = blob.generate_signed_url(expiration=timedelta(minutes=5))

    cmd = [
        "ffprobe", 
        "-v", "error", 
        "-show_entries", "format=duration", 
        "-of", "default=noprint_wrappers=1:nokey=1", 
        signed_url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        logger.error(f"Failed to get audio duration: {e}")
        raise ValueError(f"Could not determine audio duration for {gcs_uri}")


def process_chunks_locally(chunks: List[Dict], subject: str, exam_window: str):
    """
    Process chunks using ThreadPoolExecutor within this same container.
    """
    
    def process_one(chunk):
        try:
            signal_extraction.process_chunk_internal(
                session_id=chunk["session_id"],
                audio_chunk_id=chunk["chunk_id"],
                gcs_chunk_url=chunk["gcs_chunk_url"],
                start_offset_sec=chunk["start_offset_sec"],
                duration_sec=chunk["duration_sec"],
                subject_name=subject,
                exam_window=exam_window
            )
        except Exception as e:
            logger.error(f"Error processing chunk {chunk['chunk_id']}: {e}")
            # Depending on policy, we might want to fail the whole session or continue partially.
            # Continue for now.

    # Max workers: 50 threads. 
    # Since ffmpeg copy is IO bound and Gemini is IO bound, 50 is safe on 2-4 vCPU.
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(process_one, chunk) for chunk in chunks]
        concurrent.futures.wait(futures)

