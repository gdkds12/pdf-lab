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
    REASONING_MODEL_NAME = os.getenv("REASONING_MODEL_NAME", "gemini-2.5-flash")
    REASONING_THINKING_BUDGET = int(os.getenv("REASONING_THINKING_BUDGET", "1024"))
    REASONING_MAX_OUTPUT_TOKENS = int(os.getenv("REASONING_MAX_OUTPUT_TOKENS", "1200"))
    PHASE4_COST_BUDGET_KRW = float(os.getenv("PHASE4_COST_BUDGET_KRW", "1000"))
    # Rough price model (KRW / 1M tokens) for budget guard. Tune via env as pricing changes.
    REASONING_INPUT_KRW_PER_1M = float(os.getenv("REASONING_INPUT_KRW_PER_1M", "400"))
    REASONING_OUTPUT_KRW_PER_1M = float(os.getenv("REASONING_OUTPUT_KRW_PER_1M", "2400"))

    # Vertex AI Location Override (Separate from GCP_LOCATION sometimes needed)
    VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
    EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "gemini-embedding-001")
    EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))
    
    # Pipeline Settings
    INGEST_BATCH_PAGES = int(os.getenv("INGEST_BATCH_PAGES", "20"))
    EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "16"))
    PHASE1_SCANNED_MAX_WORKERS = int(os.getenv("PHASE1_SCANNED_MAX_WORKERS", "1000"))
    PHASE1_API_MAX_CONCURRENCY = int(os.getenv("PHASE1_API_MAX_CONCURRENCY", "1000"))
    PHASE1_EFFECTIVE_MAX_WORKERS = int(os.getenv("PHASE1_EFFECTIVE_MAX_WORKERS", "256"))
    PHASE1_OCR_TIMEOUT_SEC = int(os.getenv("PHASE1_OCR_TIMEOUT_SEC", "90"))
    # 1 initial call + up to 3 retries (default 4 attempts total)
    PHASE1_OCR_MAX_ATTEMPTS = int(os.getenv("PHASE1_OCR_MAX_ATTEMPTS", "4"))
    PHASE1_PARTIAL_FILL_ENABLED = os.getenv("PHASE1_PARTIAL_FILL_ENABLED", "true").lower() in ("1", "true", "yes")
    PHASE1_PARTIAL_FILL_MIN_PAGES = int(os.getenv("PHASE1_PARTIAL_FILL_MIN_PAGES", "3"))
    PHASE1_PER_PAGE_ALLOW_EMPTY_FILL = os.getenv("PHASE1_PER_PAGE_ALLOW_EMPTY_FILL", "true").lower() in ("1", "true", "yes")
    PHASE1_STRAGGLER_HEDGE_ENABLED = os.getenv("PHASE1_STRAGGLER_HEDGE_ENABLED", "true").lower() in ("1", "true", "yes")
    PHASE1_STRAGGLER_HEDGE_SEC = float(os.getenv("PHASE1_STRAGGLER_HEDGE_SEC", "45"))
    PHASE1_STRAGGLER_HEDGE_REMAINING_THRESHOLD = int(os.getenv("PHASE1_STRAGGLER_HEDGE_REMAINING_THRESHOLD", "64"))
    PHASE1_STRAGGLER_MAX_HEDGES_PER_PAGE = int(os.getenv("PHASE1_STRAGGLER_MAX_HEDGES_PER_PAGE", "1"))
    PHASE1_ADAPTIVE_SPLIT_ON_FAILURE = os.getenv("PHASE1_ADAPTIVE_SPLIT_ON_FAILURE", "true").lower() in ("1", "true", "yes")
    PHASE1_ADAPTIVE_MIN_BATCH_PAGES = int(os.getenv("PHASE1_ADAPTIVE_MIN_BATCH_PAGES", "5"))
    PHASE1_USE_BATCH_API = os.getenv("PHASE1_USE_BATCH_API", "false").lower() in ("1", "true", "yes")
    PHASE1_BATCH_REQUESTS_PER_JOB = int(os.getenv("PHASE1_BATCH_REQUESTS_PER_JOB", "10"))
    PHASE1_BATCH_MAX_INFLIGHT_JOBS = int(os.getenv("PHASE1_BATCH_MAX_INFLIGHT_JOBS", "1000"))
    # Limit concurrent PDF slicing/materialization to reduce peak memory.
    PHASE1_SLICE_MAX_INFLIGHT = int(os.getenv("PHASE1_SLICE_MAX_INFLIGHT", "8"))
    PHASE3_MAX_WORKERS = int(os.getenv("PHASE3_MAX_WORKERS", "8"))
    PHASE2_MAX_WORKERS = int(os.getenv("PHASE2_MAX_WORKERS", "12"))
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
    PHASE4_REASONING_MAX_ATTEMPTS = int(os.getenv("PHASE4_REASONING_MAX_ATTEMPTS", "3"))
    PHASE4_REASONING_RETRY_BASE_SEC = float(os.getenv("PHASE4_REASONING_RETRY_BASE_SEC", "2.0"))
    PHASE4_V2_ENABLED = os.getenv("PHASE4_V2_ENABLED", "true").lower() in ("1", "true", "yes")
    PHASE4_V2_MAX_CHUNKS = int(os.getenv("PHASE4_V2_MAX_CHUNKS", "120"))
    PHASE4_V2_MAX_CHARS_PER_CHUNK = int(os.getenv("PHASE4_V2_MAX_CHARS_PER_CHUNK", "1200"))
    PHASE4_PAGE_SEARCH_RADIUS = int(os.getenv("PHASE4_PAGE_SEARCH_RADIUS", "4"))
    PHASE4_PAGE_SEARCH_MAX_PER_SIGNAL = int(os.getenv("PHASE4_PAGE_SEARCH_MAX_PER_SIGNAL", "8"))
    PHASE4_MIN_RECOMMENDATIONS = int(os.getenv("PHASE4_MIN_RECOMMENDATIONS", "10"))
    
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
