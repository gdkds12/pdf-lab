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
    
    # JSON payload structure for the job
    payload = f'{{"source_id": "{source_id}", "gcs_pdf_url": "gs://project-thunder-assets-pdf-lab-468815/sample-image.pdf"}}'
    
    # Escape quotes for shell if needed, but for now just print raw
    print(f"\n[Test Command]:")
    print(f"python -m src.main --phase 1 --job-payload '{payload}'")

if __name__ == "__main__":
    setup()
