import sys
import os
import uuid
import asyncio

# Ensure src module can be found
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.shared.db import get_supabase_client

def setup():
    supabase = get_supabase_client()
    user_id = str(uuid.uuid4()) # Dummy user
    
    print(f"Using Dummy User ID: {user_id}")
    
    # 1. Create Subject
    subject_data = {
        "user_id": user_id,
        "name": "Phase 1 Test Subject"
    }
    res = supabase.table("subjects").insert(subject_data).execute()
    # supabase-py returns a response object with .data
    if not res.data:
        print("Error creating subject:", res)
        return
        
    subject_id = res.data[0]['subject_id']
    print(f"Created Subject: {subject_id}")
    
    # 2. Create Source
    source_data = {
        "user_id": user_id,
        "subject_id": subject_id,
        "kind": "textbook",
        "title": "Sample Image PDF",
        "gcs_pdf_url": "gs://project-thunder-assets-pdf-lab-468815/sample-image.pdf",
        "ingest_status": "queued",
        "page_count": 0
    }
    res = supabase.table("sources").insert(source_data).execute()
    if not res.data:
        print("Error creating source:", res)
        return

    source_id = res.data[0]['source_id']
    print(f"Created Source: {source_id}")
    
    # 3. Create Session (Added for Phase 4 testing)
    session_data = {
        "user_id": user_id,
        "subject_id": subject_id,
        "exam_window": "midterm",
        "gcs_audio_url": "gs://test_sample_audio/dummy.m4a",
        "status": "queued"
    }
    res = supabase.table("sessions").insert(session_data).execute()
    if not res.data:
        print("Error creating session:", res)
        return
        
    session_id = res.data[0]['session_id']
    print(f"Created Session: {session_id}")
    
    # 4. Create Audio Chunk & Signal (Added for Phase 4 testing to trigger reasoning)
    chunk_data = {
        "session_id": session_id,
        "chunk_index": 0,
        "gcs_chunk_url": "gs://test_sample_audio/dummy_chunk.m4a",
        #"transcript": "This is a dummy transcript about circuit theory.",
        "start_offset_sec": 0.0,
        "duration_sec": 10.0
    }
    res = supabase.table("audio_chunks").insert(chunk_data).execute()
    if not res.data:
        print("Error creating audio chunk:", res)
        return
    chunk_id = res.data[0]['chunk_id']
    print(f"Created Audio Chunk: {chunk_id}")
    
    signal_data = {
        "session_id": session_id,
        "audio_chunk_id": chunk_id,
        "chunk_index": 0,
        "signal_type": "likely",
        "content": "The professor mentioned KCL is important for node analysis.",
        "search_queries": ["KCL node analysis"],
        "t0_sec": 1.0,
        "t1_sec": 5.0,
        "importance": 0.9
    }
    res = supabase.table("signals").insert(signal_data).execute()
    if not res.data:
        print("Error creating signal:", res)
        return
    signal_id = res.data[0]['signal_id']
    print(f"Created Signal: {signal_id}")

    # JSON payload structure for the job (Phase 4)
    # Note: Phase 4 reasoning typically doesn't need pdf_id in payload if looking up by session -> subject -> sources
    # But checking reasoning_pipeline argument parsing might be useful.
    # We will provide basic required fields.
    
    payload = f'{{"user_id": "{user_id}", "session_id": "{session_id}", "action": "reasoning", "pdf_id": "dummy"}}'
    
    print(f"\n[Test Command Phase 4]:")
    print(f"python -m src.main --phase 4 --job-payload '{payload}'")
    
    # Also print for env file
    print(f"\n[ENV VAR]:")
    print(f"JOB_PAYLOAD='{payload}'")

if __name__ == "__main__":
    setup()
