import json
import logging
import time
from typing import Iterable, List, Optional

from google import genai
from google.genai import types

from src.shared.config import Config

logger = logging.getLogger(__name__)


class GeminiBatchError(RuntimeError):
    pass


def require_gemini_api_key() -> str:
    api_key = (Config.GEMINI_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is required for Gemini API calls. "
            "Set GEMINI_API_KEY in runtime environment."
        )
    return api_key


def get_gemini_api_client() -> genai.Client:
    return genai.Client(api_key=require_gemini_api_key())


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
