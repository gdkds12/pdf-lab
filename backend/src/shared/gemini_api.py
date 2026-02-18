import json
import logging
import time
import itertools
import threading
from typing import Iterable, List, Optional, Tuple

from google import genai
from google.genai import types

from src.shared.config import Config

logger = logging.getLogger(__name__)


class GeminiBatchError(RuntimeError):
    pass


_client_cache = {}
_client_cache_lock = threading.Lock()
_rr_counter = itertools.count()


def _collect_gemini_api_keys() -> List[str]:
    keys: List[str] = []

    primary = (Config.GEMINI_API_KEY or "").strip()
    secondary = (Config.GEMINI_API_KEY_SECONDARY or "").strip()
    if primary:
        keys.append(primary)
    if secondary:
        keys.append(secondary)

    csv_keys = (Config.GEMINI_API_KEYS or "").strip()
    if csv_keys:
        keys.extend([k.strip() for k in csv_keys.split(",") if k.strip()])

    # Deduplicate while preserving order.
    deduped: List[str] = []
    seen = set()
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        deduped.append(key)
    return deduped


def require_gemini_api_keys() -> List[str]:
    keys = _collect_gemini_api_keys()
    if not keys:
        raise RuntimeError(
            "At least one Gemini API key is required. "
            "Set GEMINI_API_KEY (and optionally GEMINI_API_KEY_SECONDARY / GEMINI_API_KEYS)."
        )
    return keys


def _pick_api_key(keys: List[str], shard_key: Optional[str]) -> str:
    if len(keys) == 1:
        return keys[0]
    if shard_key:
        idx = abs(hash(str(shard_key))) % len(keys)
        return keys[idx]
    idx = next(_rr_counter) % len(keys)
    return keys[idx]


def get_gemini_api_client(
    shard_key: Optional[str] = None,
    timeout_sec: Optional[int] = None,
) -> genai.Client:
    keys = require_gemini_api_keys()
    selected = _pick_api_key(keys, shard_key)
    timeout_value = int(timeout_sec) if timeout_sec and int(timeout_sec) > 0 else None
    cache_key: Tuple[str, Optional[int]] = (selected, timeout_value)

    with _client_cache_lock:
        cached = _client_cache.get(cache_key)
        if cached is not None:
            return cached
        client_kwargs = {"api_key": selected}
        if timeout_value is not None:
            # Route timeout through underlying HTTP client args (seconds).
            # Direct HttpOptions.timeout can behave too aggressively for large multipart uploads.
            client_kwargs["http_options"] = types.HttpOptions(clientArgs={"timeout": timeout_value})
        client = genai.Client(**client_kwargs)
        _client_cache[cache_key] = client
        return client


def normalize_model_name(model_name: str) -> str:
    name = (model_name or "").strip()
    if not name:
        raise ValueError("Model name is empty")
    return name


def _state_value(state: object) -> str:
    if hasattr(state, "value"):
        return str(getattr(state, "value"))
    return str(state)


def wait_for_batch_completion(
    client: genai.Client,
    batch_name: str,
    timeout_sec: int,
    poll_interval_sec: float,
):
    deadline = time.monotonic() + max(1, timeout_sec)
    poll_sec = max(0.5, poll_interval_sec)

    while True:
        job = client.batches.get(name=batch_name)
        state = _state_value(job.state)
        logger.info(f"Batch job {batch_name} state={state}")

        if state in ("JOB_STATE_SUCCEEDED", "JOB_STATE_PARTIALLY_SUCCEEDED"):
            return job
        if state in ("JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"):
            message = getattr(getattr(job, "error", None), "message", None) or "unknown error"
            raise GeminiBatchError(f"Batch job failed state={state}: {message}")

        if time.monotonic() >= deadline:
            raise TimeoutError(f"Batch job timeout after {timeout_sec}s: {batch_name}")

        time.sleep(poll_sec)


def parse_json_text(text: str) -> dict:
    return json.loads(text)


def extract_generate_content_text(response_obj) -> str:
    if response_obj is None:
        return ""

    text = getattr(response_obj, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    candidates = getattr(response_obj, "candidates", None)
    if not candidates:
        return ""

    chunks: List[str] = []
    for cand in candidates:
        content = getattr(cand, "content", None)
        if not content:
            continue
        parts = getattr(content, "parts", None) or []
        for part in parts:
            value = getattr(part, "text", None)
            if isinstance(value, str):
                chunks.append(value)
    return "\n".join(chunks).strip()


def chunked(items: List, size: int) -> Iterable[List]:
    n = max(1, int(size))
    for i in range(0, len(items), n):
        yield items[i : i + n]
