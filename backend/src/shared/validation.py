import json
from typing import Any, Dict, List
from uuid import UUID


def parse_payload(payload_str: str) -> Dict[str, Any]:
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON payload") from exc
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object")
    return payload


def require_uuid(payload: Dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing {key} in payload")
    raw = value.strip()
    try:
        return str(UUID(raw))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {key} UUID: {raw}") from exc


def require_uuid_list(payload: Dict[str, Any], key: str, fallback_key: str = "") -> List[str]:
    values = payload.get(key)
    if (not values) and fallback_key and payload.get(fallback_key):
        values = [payload.get(fallback_key)]
    if not isinstance(values, list) or not values:
        raise ValueError(f"Missing {key} within payload")

    normalized: List[str] = []
    for item in values:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{key} contains an empty or non-string value")
        raw = item.strip()
        try:
            normalized.append(str(UUID(raw)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid UUID in {key}: {raw}") from exc
    return normalized


def require_gcs_uri(payload: Dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing {key} in payload")
    uri = value.strip()
    if not uri.startswith("gs://"):
        raise ValueError(f"Invalid {key}: must start with gs://")
    path = uri[len("gs://"):]
    if "/" not in path:
        raise ValueError(f"Invalid {key}: object path is required")
    return uri
