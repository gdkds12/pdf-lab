import os
import logging
from dotenv import load_dotenv

# Load .env file from backend root (assuming we run from backend/)
load_dotenv()

class Config:
    GCP_PROJECT = os.getenv("GCP_PROJECT", "project-thunder-v3")
    GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
    GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
    
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    # Prefer SUPABASE_SERVICE_ROLE_KEY, fall back to SUPABASE_KEY
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    
    # Gemini Configuration
    GEMINI_LOCATION = "us-central1"
    GEMINI_MODEL_NAME = "gemini-2.5-flash-lite"
    REASONING_MODEL_NAME = "gemini-3.0-flash"

    # Vertex AI Location Override (Separate from GCP_LOCATION sometimes needed)
    VERTEX_LOCATION = "us-central1" 
    EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-004")
    
    # Pipeline Settings
    INGEST_BATCH_PAGES = int(os.getenv("INGEST_BATCH_PAGES", "20"))
    EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "8"))
    
    @classmethod
    def validate(cls):
        required = ["SUPABASE_URL", "SUPABASE_KEY", "GCP_PROJECT"]
        missing = [k for k in required if not getattr(cls, k) and not os.getenv(k)]
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
