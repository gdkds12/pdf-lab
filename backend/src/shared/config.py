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
    # For Gemini 2.x/2.5 standard paygo, prefer global endpoint for better pool access.
    GEMINI_LOCATION = os.getenv("GEMINI_LOCATION", "global")
    GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-lite")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_API_KEY_SECONDARY = os.getenv("GEMINI_API_KEY_SECONDARY")
    # Optional comma-separated key list for multi-project quota sharding.
    GEMINI_API_KEYS = os.getenv("GEMINI_API_KEYS", "")
    # FORCE UPDATE TIMESTAMP 2026-01-14 16:30
    # Falling back to known valid Thinking Model
    REASONING_MODEL_NAME = os.getenv("REASONING_MODEL_NAME", "gemini-2.5-flash-lite")

    # Vertex AI Location Override (Separate from GCP_LOCATION sometimes needed)
    VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
    EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "gemini-embedding-001")
    
    # Pipeline Settings
    INGEST_BATCH_PAGES = int(os.getenv("INGEST_BATCH_PAGES", "20"))
    EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "8"))
    PHASE1_SCANNED_MAX_WORKERS = int(os.getenv("PHASE1_SCANNED_MAX_WORKERS", "12"))
    PHASE1_OCR_TIMEOUT_SEC = int(os.getenv("PHASE1_OCR_TIMEOUT_SEC", "90"))
    PHASE1_USE_BATCH_API = os.getenv("PHASE1_USE_BATCH_API", "false").lower() in ("1", "true", "yes")
    PHASE1_BATCH_REQUESTS_PER_JOB = int(os.getenv("PHASE1_BATCH_REQUESTS_PER_JOB", "10"))
    PHASE1_BATCH_MAX_INFLIGHT_JOBS = int(os.getenv("PHASE1_BATCH_MAX_INFLIGHT_JOBS", "3"))
    PHASE3_MAX_WORKERS = int(os.getenv("PHASE3_MAX_WORKERS", "2"))
    PHASE2_MAX_WORKERS = int(os.getenv("PHASE2_MAX_WORKERS", "4"))
    PHASE2_USE_BATCH_API = os.getenv("PHASE2_USE_BATCH_API", "false").lower() in ("1", "true", "yes")
    PHASE2_BATCH_REQUESTS_PER_JOB = int(os.getenv("PHASE2_BATCH_REQUESTS_PER_JOB", "10"))
    PHASE2_BATCH_MAX_INFLIGHT_JOBS = int(os.getenv("PHASE2_BATCH_MAX_INFLIGHT_JOBS", "3"))
    PHASE2_CHUNK_MAX_RETRIES = int(os.getenv("PHASE2_CHUNK_MAX_RETRIES", "3"))
    PHASE2_CHUNK_RETRY_BASE_SEC = float(os.getenv("PHASE2_CHUNK_RETRY_BASE_SEC", "2.0"))
    PHASE2_GEMINI_MAX_RETRIES = int(os.getenv("PHASE2_GEMINI_MAX_RETRIES", "5"))
    PHASE2_GEMINI_RETRY_BASE_SEC = float(os.getenv("PHASE2_GEMINI_RETRY_BASE_SEC", "2.0"))
    PHASE2_GEMINI_RETRY_MAX_SEC = float(os.getenv("PHASE2_GEMINI_RETRY_MAX_SEC", "30.0"))
    GEMINI_BATCH_POLL_SEC = float(os.getenv("GEMINI_BATCH_POLL_SEC", "5.0"))
    GEMINI_BATCH_TIMEOUT_SEC = int(os.getenv("GEMINI_BATCH_TIMEOUT_SEC", "1800"))

    # Guardrail / Compliance Settings
    DELETE_SOURCE_ASSETS_ON_SUCCESS = os.getenv("DELETE_SOURCE_ASSETS_ON_SUCCESS", "false").lower() in ("1", "true", "yes")
    PHASE4_VERBATIM_WINDOW = int(os.getenv("PHASE4_VERBATIM_WINDOW", "80"))
    PHASE4_MAX_TITLE_LEN = int(os.getenv("PHASE4_MAX_TITLE_LEN", "60"))
    PHASE4_MAX_WHY_LEN = int(os.getenv("PHASE4_MAX_WHY_LEN", "260"))
    PHASE4_MAX_AUDIO_REFS = int(os.getenv("PHASE4_MAX_AUDIO_REFS", "5"))
    PHASE4_MAX_CITATIONS = int(os.getenv("PHASE4_MAX_CITATIONS", "5"))
    PHASE4_MAX_QUEUE_ITEMS = int(os.getenv("PHASE4_MAX_QUEUE_ITEMS", "20"))
    PHASE4_STRICT_SCHEMA = os.getenv("PHASE4_STRICT_SCHEMA", "true").lower() in ("1", "true", "yes")
    
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
