import json
import logging
import os
import random
import subprocess
import time
import uuid
import traceback
import concurrent.futures
from typing import List, Dict, Any, Optional
from datetime import timedelta

import google.auth
from google.auth.transport import requests as google_requests
from google.cloud import storage
from google.genai import types
import json_repair

from src.shared.config import Config
from src.shared.db import get_supabase_client
from src.shared.gemini_api import (
    chunked,
    extract_generate_content_text,
    get_gemini_api_client,
    normalize_model_name,
    wait_for_batch_completion,
)
from src.shared.validation import parse_payload, require_gcs_uri, require_uuid

logger = logging.getLogger(__name__)

def process_chunk_internal(
    session_id: str,
    audio_chunk_id: str,
    chunk_index: Optional[int],
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
    supabase = get_supabase_client()
    _mark_audio_chunk_status(supabase, audio_chunk_id, "processing", None)

    try:
        audio_bytes, mime_type = _slice_audio_to_bytes(
            original_gcs_uri=gcs_chunk_url,
            start=start_offset_sec,
            duration=duration_sec,
            chunk_id=audio_chunk_id,
        )
        signals = _call_gemini_extraction(
            session_id=session_id,
            audio_chunk_id=audio_chunk_id,
            audio_bytes=audio_bytes,
            mime_type=mime_type,
            subject=subject_name,
            exam_window=exam_window,
        )
        _persist_signals_for_chunk(
            supabase=supabase,
            session_id=session_id,
            audio_chunk_id=audio_chunk_id,
            chunk_index=chunk_index,
            signals=signals,
        )
        _mark_audio_chunk_status(supabase, audio_chunk_id, "completed", None)
    except Exception as e:
        msg = f"Gemini Extraction Failed: {e}"
        logger.error(msg)
        _mark_audio_chunk_status(supabase, audio_chunk_id, "failed", msg)
        raise


def process_chunks_with_batch(chunks: List[Dict], subject: str, exam_window: str):
    """
    Batch mode for Phase 2.
    Submits multiple audio chunk extractions through Gemini Batch API.
    """
    if not chunks:
        return 0, []

    supabase = get_supabase_client()
    model_name = normalize_model_name(Config.GEMINI_MODEL_NAME)

    processed_count = 0
    failed_ids: List[str] = []
    request_group_size = max(1, Config.PHASE2_BATCH_REQUESTS_PER_JOB)
    groups = list(chunked(chunks, request_group_size))
    max_inflight = max(1, min(len(groups), Config.PHASE2_BATCH_MAX_INFLIGHT_JOBS))

    # Set all chunks to processing first.
    for chunk in chunks:
        _mark_audio_chunk_status(supabase, chunk["chunk_id"], "processing", None)

    logger.info(
        f"Phase2 batch mode: groups={len(groups)}, group_size={request_group_size}, max_inflight={max_inflight}"
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_inflight) as executor:
        futures = [
            executor.submit(_run_phase2_batch_group, group, subject, exam_window, model_name)
            for group in groups
        ]
        for future in concurrent.futures.as_completed(futures):
            group_processed_count, group_failed_ids = future.result()
            processed_count += group_processed_count
            failed_ids.extend(group_failed_ids)

    return processed_count, failed_ids


def run(payload_str: str):
    logger.info("Phase 2: Audio Signal Extraction Started")
    payload = parse_payload(payload_str)

    # Wrapper for single execution via CLI
    process_chunk_internal(
        session_id=require_uuid(payload, "session_id"),
        audio_chunk_id=require_uuid(payload, "audio_chunk_id"),
        chunk_index=payload.get("chunk_index"),
        gcs_chunk_url=require_gcs_uri(payload, "gcs_chunk_url"),
        start_offset_sec=payload.get("start_offset_sec", 0),
        duration_sec=payload.get("duration_sec", 0),
        subject_name=payload.get("subject", "Unknown"),
        exam_window=payload.get("exam_window", "Unknown")
    )


def _run_phase2_batch_group(
    group: List[Dict[str, Any]],
    subject: str,
    exam_window: str,
    model_name: str,
):
    supabase = get_supabase_client()
    first_chunk_id = group[0]["chunk_id"] if group else "phase2-batch"
    client = get_gemini_api_client(shard_key=f"p2-batch:{first_chunk_id}")
    requests: List[types.InlinedRequest] = []
    metas: List[Dict[str, Any]] = []
    failed_ids: List[str] = []
    processed_count = 0

    for chunk in group:
        chunk_id = chunk["chunk_id"]
        try:
            audio_bytes, mime_type = _slice_audio_to_bytes(
                original_gcs_uri=chunk["gcs_chunk_url"],
                start=float(chunk.get("start_offset_sec") or 0),
                duration=float(chunk.get("duration_sec") or 0),
                chunk_id=chunk_id,
            )
            prompt = _build_user_prompt(
                session_id=chunk["session_id"],
                audio_chunk_id=chunk_id,
                subject=subject,
                exam_window=exam_window,
            )
            requests.append(
                types.InlinedRequest(
                    contents=[
                        types.Part.from_text(text=_phase2_system_instruction()),
                        types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                        types.Part.from_text(text=prompt),
                    ],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=_phase2_response_schema(),
                            temperature=0.2,
                            max_output_tokens=2048,
                        ),
                    )
                )
            metas.append(chunk)
        except Exception as prep_err:
            err_text = f"Batch prep failed: {prep_err}"
            logger.error(f"{chunk_id}: {err_text}")
            _mark_audio_chunk_status(supabase, chunk_id, "failed", err_text)
            failed_ids.append(chunk_id)

    if not requests:
        return processed_count, failed_ids

    try:
        batch_job = client.batches.create(
            model=model_name,
            src=requests,
            config=types.CreateBatchJobConfig(
                display_name=f"p2-signal-{uuid.uuid4().hex[:8]}"
            ),
        )
        logger.info(f"Created Phase2 batch job: {batch_job.name}")
        completed = wait_for_batch_completion(
            client=client,
            batch_name=batch_job.name,
            timeout_sec=Config.GEMINI_BATCH_TIMEOUT_SEC,
            poll_interval_sec=Config.GEMINI_BATCH_POLL_SEC,
        )
        responses = list((completed.dest and completed.dest.inlined_responses) or [])
    except Exception as batch_err:
        logger.error(f"Phase2 batch job failed: {batch_err}")
        for meta in metas:
            chunk_id = meta["chunk_id"]
            _mark_audio_chunk_status(supabase, chunk_id, "failed", f"Batch failed: {batch_err}")
            failed_ids.append(chunk_id)
        return processed_count, failed_ids

    if len(responses) != len(metas):
        message = f"Batch response mismatch expected={len(metas)} got={len(responses)}"
        logger.error(message)
        for meta in metas:
            chunk_id = meta["chunk_id"]
            _mark_audio_chunk_status(supabase, chunk_id, "failed", message)
            failed_ids.append(chunk_id)
        return processed_count, failed_ids

    for idx, inlined_response in enumerate(responses):
        meta = metas[idx]
        chunk_id = meta["chunk_id"]
        try:
            if getattr(inlined_response, "error", None):
                err_text = getattr(inlined_response.error, "message", None) or str(inlined_response.error)
                raise RuntimeError(err_text)

            text = extract_generate_content_text(getattr(inlined_response, "response", None))
            if not text:
                raise RuntimeError("empty response")

            parsed = json_repair.loads(text)
            signals = parsed.get("signals", [])
            _persist_signals_for_chunk(
                supabase=supabase,
                session_id=meta["session_id"],
                audio_chunk_id=chunk_id,
                chunk_index=meta.get("chunk_index"),
                signals=signals,
            )
            _mark_audio_chunk_status(supabase, chunk_id, "completed", None)
            processed_count += 1
        except Exception as e:
            logger.error(f"Batch response handling failed for chunk {chunk_id}: {e}")
            _mark_audio_chunk_status(supabase, chunk_id, "failed", str(e))
            failed_ids.append(chunk_id)

    return processed_count, failed_ids


def _mark_audio_chunk_status(supabase, audio_chunk_id: str, status: str, error_message: Optional[str]):
    try:
        payload = {"status": status, "error_message": error_message}
        supabase.table("audio_chunks").update(payload).eq("chunk_id", audio_chunk_id).execute()
    except Exception as e:
        logger.warning(f"Could not update status for chunk {audio_chunk_id}: {e}")


def _persist_signals_for_chunk(
    supabase,
    session_id: str,
    audio_chunk_id: str,
    chunk_index: Optional[int],
    signals: List[Dict[str, Any]],
):
    if not signals:
        logger.info(f"Chunk {audio_chunk_id}: No signals extracted.")
        supabase.table("signals").delete().eq("audio_chunk_id", audio_chunk_id).execute()
        return

    validated_signals = _validate_signals(signals, audio_chunk_id, chunk_index)
    if not validated_signals:
        logger.info(f"Chunk {audio_chunk_id}: No valid signals after server-side validation.")
        supabase.table("signals").delete().eq("audio_chunk_id", audio_chunk_id).execute()
        return

    for sig in validated_signals:
        sig["session_id"] = session_id
    supabase.table("signals").delete().eq("audio_chunk_id", audio_chunk_id).execute()
    data = supabase.table("signals").insert(validated_signals).execute()
    logger.info(f"Chunk {audio_chunk_id}: Inserted {len(data.data)} signals. (raw={len(signals)})")


def _generate_signed_read_url(gcs_uri: str, expiration_minutes: int = 15) -> str:
    storage_client = storage.Client(project=Config.GCP_PROJECT)
    bucket_name = gcs_uri.replace("gs://", "").split("/")[0]
    blob_name = "/".join(gcs_uri.replace("gs://", "").split("/")[1:])
    bucket = storage_client.bucket(bucket_name)
    source_blob = bucket.blob(blob_name)
    credentials, _ = google.auth.default()

    if hasattr(credentials, "service_account_email") and credentials.service_account_email:
        request = google_requests.Request()
        credentials.refresh(request)
        return source_blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            service_account_email=credentials.service_account_email,
            access_token=credentials.token
        )
    return source_blob.generate_signed_url(expiration=timedelta(minutes=expiration_minutes))


def _determine_audio_mime_type(gcs_uri: str) -> str:
    ext = os.path.splitext(gcs_uri)[1].lower()
    if ext == ".m4a":
        return "audio/mp4"
    if ext == ".wav":
        return "audio/wav"
    if ext == ".aac":
        return "audio/aac"
    if ext == ".ogg":
        return "audio/ogg"
    return "audio/mpeg"


def _slice_audio_to_bytes(original_gcs_uri: str, start: float, duration: float, chunk_id: str):
    """
    Slice audio locally via ffmpeg stream copy and return bytes + mime type.
    """
    storage_client = storage.Client(project=Config.GCP_PROJECT)
    bucket_name = original_gcs_uri.replace("gs://", "").split("/")[0]
    blob_name = "/".join(original_gcs_uri.replace("gs://", "").split("/")[1:])

    _, ext = os.path.splitext(blob_name)
    if not ext:
        ext = ".mp3"

    local_output = f"/tmp/{chunk_id}{ext}"

    try:
        if duration > 0:
            input_url = _generate_signed_read_url(original_gcs_uri, expiration_minutes=15)
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(max(0.0, start)),
                "-t", str(max(0.0, duration)),
                "-i", input_url,
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                local_output
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            with open(local_output, "rb") as f:
                return f.read(), _determine_audio_mime_type(original_gcs_uri)

        blob = storage_client.bucket(bucket_name).blob(blob_name)
        return blob.download_as_bytes(), _determine_audio_mime_type(original_gcs_uri)
    finally:
        try:
            if os.path.exists(local_output):
                os.remove(local_output)
        except OSError:
            pass


def _phase2_response_schema() -> Dict[str, Any]:
    return {
        "type": "OBJECT",
        "required": ["signals"],
        "properties": {
            "signals": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "required": [
                        "signal_type",
                        "content",
                        "search_queries",
                        "audio_chunk_id",
                        "t0_sec",
                        "t1_sec",
                        "importance",
                    ],
                    "properties": {
                        "signal_type": {"type": "STRING", "enum": ["hint", "priority", "trap", "repeat"]},
                        "content": {"type": "STRING"},
                        "search_queries": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "audio_chunk_id": {"type": "STRING"},
                        "t0_sec": {"type": "NUMBER", "minimum": 0},
                        "t1_sec": {"type": "NUMBER", "minimum": 0},
                        "importance": {"type": "NUMBER", "minimum": 0, "maximum": 1},
                    },
                },
            }
        },
    }


def _phase2_system_instruction() -> str:
    return """
[ROLE]
You are a lecture signal analyzer. Your job is ONLY to extract professor hints from lecture audio and generate textbook search intents for study recommendations.

[NON_NEGOTIABLES]
- Output MUST be a SINGLE valid JSON object matching the provided JSON Schema.
- **MAX SIGNALS**: Extract no more than 8 most important signals per input to prevent loops.
- **NO REPETITION**: If a similar concept appears multiple times, merge them into ONE signal with the most representative time range.
- **STRICT TERMINATION**: Stop immediately after the closing "}".
- If no signals are found in the input, return {"signals": []}.
- Do NOT make any final exam predictions.
- Do NOT guess textbook pages/citations/source IDs/chunk IDs.
- content MUST be Korean.

[REQUIRED_OUTPUT_STRUCTURE]
Each signal item requires:
- signal_type: hint|priority|trap|repeat
- content: Korean summary (max 160 chars)
- search_queries: 2~6 keywords
- audio_chunk_id: exact ID from input
- t0_sec, t1_sec: float
- importance: 0.0~1.0
"""


def _build_user_prompt(session_id: str, audio_chunk_id: str, subject: str, exam_window: str) -> str:
    return f"""
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


def _call_gemini_extraction(
    session_id: str,
    audio_chunk_id: str,
    audio_bytes: bytes,
    mime_type: str,
    subject: str,
    exam_window: str
) -> List[Dict[str, Any]]:
    client = get_gemini_api_client(shard_key=f"p2-sync:{audio_chunk_id}")
    model_name = normalize_model_name(Config.GEMINI_MODEL_NAME)
    prompt = _build_user_prompt(session_id, audio_chunk_id, subject, exam_window)
    audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)

    max_retries = max(1, Config.PHASE2_GEMINI_MAX_RETRIES)
    retry_base_sec = max(0.5, float(Config.PHASE2_GEMINI_RETRY_BASE_SEC))
    retry_max_sec = max(1.0, float(Config.PHASE2_GEMINI_RETRY_MAX_SEC))

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[_phase2_system_instruction(), audio_part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_phase2_response_schema(),
                    temperature=0.2,
                    max_output_tokens=2048,
                ),
            )

            text = response.text or extract_generate_content_text(response)
            logger.info(f"Gemini Phase 2 Response: {(text or '')[:200]}...")

            if not text:
                return []
            data = json_repair.loads(text)
            return data.get("signals", [])

        except Exception as e:
            if attempt < max_retries and _is_retryable_generation_error(e):
                sleep_sec = min(retry_max_sec, retry_base_sec * (2 ** (attempt - 1))) + random.uniform(0, 1.0)
                logger.warning(
                    f"Transient Gemini error for chunk {audio_chunk_id}. "
                    f"retrying in {sleep_sec:.1f}s ({attempt}/{max_retries}): {e}"
                )
                time.sleep(sleep_sec)
                continue

            logger.error(f"Error during Gemini generation: {type(e).__name__}: {e}")
            logger.error(traceback.format_exc())
            raise

    return []


def _is_retryable_generation_error(error: Exception) -> bool:
    text = str(error).lower()
    retry_tokens = (
        "429",
        "resource exhausted",
        "rate limit",
        "quota",
        "deadline exceeded",
        "timeout",
        "service unavailable",
        "temporarily unavailable",
        "internal",
    )
    return any(token in text for token in retry_tokens)


def _normalize_search_queries(queries: Any) -> List[str]:
    if not isinstance(queries, list):
        return []
    cleaned = []
    seen = set()
    for q in queries:
        if not isinstance(q, str):
            continue
        nq = " ".join(q.strip().split())
        if len(nq) < 2 or len(nq) > 120:
            continue
        key = nq.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(nq)
    return cleaned


def _validate_signals(raw_signals: List[Dict[str, Any]], audio_chunk_id: str, chunk_index: Optional[int]) -> List[Dict[str, Any]]:
    valid_signal_types = {"hint", "priority", "trap", "repeat"}
    validated: List[Dict[str, Any]] = []

    for sig in raw_signals:
        signal_type = sig.get("signal_type")
        if signal_type not in valid_signal_types:
            continue

        content = sig.get("content", "")
        if not isinstance(content, str):
            continue
        content = " ".join(content.strip().split())
        if not content:
            continue
        if len(content) > 200:
            content = content[:200]

        queries = _normalize_search_queries(sig.get("search_queries", []))
        if len(queries) < 2:
            continue
        queries = queries[:6]

        t0 = sig.get("t0_sec")
        t1 = sig.get("t1_sec")
        if not isinstance(t0, (int, float)) or not isinstance(t1, (int, float)):
            continue
        if t0 < 0 or t1 < 0 or t0 > t1:
            continue

        importance = sig.get("importance")
        if not isinstance(importance, (int, float)):
            importance = 0.5
        importance = float(max(0.0, min(1.0, importance)))

        cleaned = {
            "signal_type": signal_type,
            "content": content,
            "search_queries": queries,
            "audio_chunk_id": audio_chunk_id,
            "t0_sec": float(t0),
            "t1_sec": float(t1),
            "importance": importance
        }
        if chunk_index is not None:
            cleaned["chunk_index"] = int(chunk_index)

        validated.append(cleaned)

    return validated
