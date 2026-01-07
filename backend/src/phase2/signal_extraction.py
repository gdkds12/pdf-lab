import json
import logging
import os
import subprocess
import uuid
import traceback
from typing import List, Dict, Any, Optional
from datetime import timedelta
from google.cloud import storage

import vertexai
from vertexai.generative_models import GenerativeModel, Part
from src.shared.config import Config
from src.shared.db import get_supabase_client

logger = logging.getLogger(__name__)

def process_chunk_internal(
    session_id: str,
    audio_chunk_id: str,
    gcs_chunk_url: str,
    start_offset_sec: float,
    duration_sec: float,
    subject_name: str,
    exam_window: str
):
    """
    Internal function to process a single chunk.
    Designed to be called by Dispatcher directly in a ThreadPool.
    """
    vertexai.init(project=Config.GCP_PROJECT, location=Config.GCP_LOCATION)
    supabase = get_supabase_client()
    
    # 0. Update Status: Processing
    try:
        supabase.table("audio_chunks").update({
            "status": "processing",
            "error_message": None
        }).eq("chunk_id", audio_chunk_id).execute()
    except Exception as e:
        logger.warning(f"Could not update status to processing: {e}")

    processed_gcs_uri = gcs_chunk_url
    temp_gcs_blob = None
    
    # SLICING LOGIC
    if duration_sec > 0:
        try:
            processed_gcs_uri = _slice_and_upload_audio(gcs_chunk_url, start_offset_sec, duration_sec, audio_chunk_id)
            if processed_gcs_uri != gcs_chunk_url:
                temp_gcs_blob = processed_gcs_uri
        except Exception as e:
            msg = f"Failed to slice audio for chunk {audio_chunk_id}: {e}"
            logger.error(msg)
            supabase.table("audio_chunks").update({"status": "failed", "error_message": msg}).eq("chunk_id", audio_chunk_id).execute()
            raise

    try:
        signals = _call_gemini_extraction(
            session_id=session_id,
            audio_chunk_id=audio_chunk_id,
            gcs_uri=processed_gcs_uri,
            subject=subject_name,
            exam_window=exam_window
        )
        
        # Success if we reach here (even if no signals)
        supabase.table("audio_chunks").update({"status": "completed"}).eq("chunk_id", audio_chunk_id).execute()
        
    except Exception as e:
        msg = f"Gemini Extraction Failed: {e}"
        logger.error(msg)
        supabase.table("audio_chunks").update({"status": "failed", "error_message": msg}).eq("chunk_id", audio_chunk_id).execute()
        # Clean up temp file
        if temp_gcs_blob:
            _delete_gcs_file(temp_gcs_blob)
        raise

    finally:
        # Cleanup temp file
        if temp_gcs_blob:
            _delete_gcs_file(temp_gcs_blob)

    if signals:
        try:
            for sig in signals:
                sig["session_id"] = session_id
                # Adjust timestamps relative to original file
                sig["t0_sec"] = sig.get("t0_sec", 0) + start_offset_sec
                sig["t1_sec"] = sig.get("t1_sec", 0) + start_offset_sec
                
                if sig.get("audio_chunk_id") != audio_chunk_id:
                    sig["audio_chunk_id"] = audio_chunk_id

            data = supabase.table("signals").insert(signals).execute()
            logger.info(f"Chunk {audio_chunk_id}: Inserted {len(data.data)} signals.")
        except Exception as e:
            logger.error(f"Failed to insert signals for chunk {audio_chunk_id}: {e}")
            raise
    else:
        logger.info(f"Chunk {audio_chunk_id}: No signals extracted.")


def run(payload_str: str):
    logger.info("Phase 2: Audio Signal Extraction Started")
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON payload")

    # Wrapper for single execution via CLI
    process_chunk_internal(
        session_id=payload.get("session_id"),
        audio_chunk_id=payload.get("audio_chunk_id"),
        gcs_chunk_url=payload.get("gcs_chunk_url"),
        start_offset_sec=payload.get("start_offset_sec", 0),
        duration_sec=payload.get("duration_sec", 0),
        subject_name=payload.get("subject", "Unknown"),
        exam_window=payload.get("exam_window", "Unknown")
    )


def _slice_and_upload_audio(original_gcs_uri: str, start: float, duration: float, chunk_id: str) -> str:
    """
    Slices audio using ffmpeg stream copy (-c copy) for speed.
    """
    storage_client = storage.Client(project=Config.GCP_PROJECT)
    
    bucket_name = original_gcs_uri.replace("gs://", "").split("/")[0]
    blob_name = "/".join(original_gcs_uri.replace("gs://", "").split("/")[1:])
    
    bucket = storage_client.bucket(bucket_name)
    source_blob = bucket.blob(blob_name)

    # Check for service account credentials to handle signing in Cloud Run
    import google.auth
    from google.auth.transport import requests as google_requests
    credentials, _ = google.auth.default()
    
    # In Cloud Run (Compute Engine creds), we use Access Token + Service Account Email
    if hasattr(credentials, "service_account_email") and credentials.service_account_email:
        request = google_requests.Request()
        credentials.refresh(request)
        input_url = source_blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            service_account_email=credentials.service_account_email,
            access_token=credentials.token
        )
    else:
         input_url = source_blob.generate_signed_url(expiration=timedelta(minutes=15))
    
    # Determine extension from source file to allow "copy" codec (e.g. m4a -> m4a)
    _, ext = os.path.splitext(blob_name)
    if not ext:
        ext = ".mp3" # Fallback
        
    local_output = f"/tmp/{chunk_id}{ext}"
    
    # Use -c copy for blazing fast processing (no decoding/encoding)
    # Note: -ss before -i for input seeking is fast.
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-t", str(duration),
        "-i", input_url,
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        local_output
    ]
    
    logger.info(f"Running ffmpeg copy from {ext} to {ext}")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    
    # Upload to Temp GCS
    dest_blob_name = f"temp_chunks/{chunk_id}{ext}"
    dest_blob = storage_client.bucket(bucket_name).blob(dest_blob_name)
    dest_blob.upload_from_filename(local_output)
    
    os.remove(local_output)
    
    return f"gs://{bucket_name}/{dest_blob_name}"

def _delete_gcs_file(gcs_uri: str):
    try:
        storage_client = storage.Client(project=Config.GCP_PROJECT)
        bucket_name = gcs_uri.replace("gs://", "").split("/")[0]
        blob_name = "/".join(gcs_uri.replace("gs://", "").split("/")[1:])
        storage_client.bucket(bucket_name).blob(blob_name).delete()
        logger.info(f"Deleted temp file {gcs_uri}")
    except Exception as e:
        logger.warning(f"Failed to delete temp file {gcs_uri}: {e}")


def _call_gemini_extraction(
    session_id: str, 
    audio_chunk_id: str, 
    gcs_uri: str, 
    subject: str, 
    exam_window: str
) -> List[Dict[str, Any]]:
    
    model_name = Config.GEMINI_MODEL_NAME # e.g. "gemini-2.5-flash-lite"
    model = GenerativeModel(model_name)

    # Response Schema
    response_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["signals"],
        "properties": {
            "signals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                "signal_type",
                "content",
                "search_queries",
                "audio_chunk_id",
                "t0_sec",
                "t1_sec",
                "importance"
                ],
                "properties": {
                "signal_type": {
                    "type": "string",
                    "enum": ["hint", "likely", "trap"]
                },
                "content": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 200
                },
                "search_queries": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 6,
                    "items": {
                    "type": "string",
                    "minLength": 2,
                    "maxLength": 120
                    }
                },
                "audio_chunk_id": {
                    "type": "string",
                    "minLength": 8,
                    "maxLength": 64
                },
                "t0_sec": { "type": "number", "minimum": 0 },
                "t1_sec": { "type": "number", "minimum": 0 },
                "importance": { "type": "number", "minimum": 0, "maximum": 1 }
                }
            }
            }
        }
    }

    # System Prompt
    system_instruction = """
[ROLE]
You are an exam-focused lecture analyzer. Your job is ONLY to extract exam-relevant signals from the provided lecture audio and generate textbook search intents.

[NON_NEGOTIABLES]
- Output MUST be a SINGLE valid JSON object matching the provided JSON Schema.
- **MAX SIGNALS**: Extract no more than 8 most important signals per input to prevent loops.
- **NO REPETITION**: If a similar concept (e.g., Ideal OP-amp conditions) appears multiple times, merge them into ONE signal with the most representative time range.
- **STRICT TERMINATION**: Stop immediately after the closing "}". Do not repeat the same signals with minor variations.
- If no signals are found in the input, return {"signals": []}.
- Do NOT make any final exam predictions. This is Phase 2 only.
- Do NOT guess textbook pages, citations, source_id, or chunk_id.
- content MUST be Korean.

[REQUIRED_OUTPUT_STRUCTURE]
You must return a JSON object with a single key "signals", which is an array of objects.
Each object in "signals" must have:
- "signal_type": one of "hint", "likely", "trap"
- "content": Korean text summarizing the signal (max 160 chars)
- "search_queries": Array of 2-6 strings (keywords for textbook search)
- "audio_chunk_id": The ID provided in the input
- "t0_sec": Start time (float)
- "t1_sec": End time (float)
- "importance": Float (0.0 to 1.0)

[LANGUAGE_POLICY]
- JSON keys must follow the schema exactly.
- signals[].content MUST be written in Korean.
- search_queries may be Korean or English keywords.

[TASK]
1. Scan the audio input for unique exam signals.
2. **Deduplication Logic**:
   - Compare new signals with already extracted ones. 
   - If the `content` or `search_queries` overlap by more than 70%, DISCARD the new one or MERGE them.
   - Do not generate multiple signals for the same virtual short circuit (V+=V-) or KCL logic unless they occur in completely different contexts.
3. Once the entire input text is scanned once, finalize the JSON and STOP.

[EXECUTION]
- You are a precise extractor, not a repetitive writer.
- Quality over quantity.
- If you have nothing new to say, end the JSON array.
"""

    # User Prompt
    prompt = f"""
### INPUT DATA:
session_id="{session_id}"
audio_chunk_id="{audio_chunk_id}"
exam_window="{exam_window}"
subject="{subject}"

Audio File To Analyze:
(See attached audio part)

### END OF INPUT data

[TASK]
Extract signals + search intent as specified.
[NOW_OUTPUT]
"""

    # Audio Part
    # Determine mime_type based on file extension
    ext = os.path.splitext(gcs_uri)[1].lower()
    mime_type = "audio/mpeg"
    if ext == ".m4a":
        mime_type = "audio/mp4"
    elif ext == ".wav":
        mime_type = "audio/wav"
    elif ext == ".aac":
        mime_type = "audio/aac"
    elif ext == ".ogg":
        mime_type = "audio/ogg"
    
    logger.info(f"Using mime_type {mime_type} for file {gcs_uri}")
    audio_part = Part.from_uri(uri=gcs_uri, mime_type=mime_type)
    
    try:
        response = model.generate_content(
            [system_instruction, audio_part, prompt],
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": response_schema,
                "temperature": 0.2,
                "max_output_tokens": 2048,
                "frequency_penalty": 0.6,
            }
        )
        
        text = response.text
        logger.info(f"Gemini Phase 2 Response: {text[:200]}...")
        
        data = json.loads(text)
        return data.get("signals", [])

    except Exception as e:
        logger.error(f"Error during Gemini generation: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        raise
