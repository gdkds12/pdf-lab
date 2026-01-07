import json
import logging
from typing import List, Dict, Any, Optional
import vertexai
from vertexai.generative_models import GenerativeModel, Part, SafetySetting, FinishReason
from src.shared.config import Config
from src.shared.db import get_supabase_client

logger = logging.getLogger(__name__)

def run(payload_str: str):
    logger.info("Phase 2: Audio Signal Extraction Started")
    
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON payload: {payload_str}")
        raise ValueError("Invalid JSON payload")

    # Required fields in payload
    session_id = payload.get("session_id")
    audio_chunk_id = payload.get("audio_chunk_id")
    gcs_chunk_url = payload.get("gcs_chunk_url") # "gs://..."

    if not all([session_id, audio_chunk_id, gcs_chunk_url]):
        logger.error(f"Missing required fields in payload: {payload}")
        raise ValueError("Missing required fields: session_id, audio_chunk_id, gcs_chunk_url")

    # Optional fields
    subject_name = payload.get("subject", "Unknown Subject")
    exam_window = payload.get("exam_window", "Unknown Exam")
    # user_notes = payload.get("user_notes", "") # Optional context if available

    # Initialize Supabase
    supabase = get_supabase_client()

    # Initialize Vertex AI
    vertexai.init(project=Config.GCP_PROJECT, location=Config.GCP_LOCATION)
    
    # 2. Gemini Reasoning
    try:
        signals = _call_gemini_extraction(
            session_id=session_id,
            audio_chunk_id=audio_chunk_id,
            gcs_uri=gcs_chunk_url,
            subject=subject_name,
            exam_window=exam_window
        )
    except Exception as e:
        logger.error(f"Gemini processing failed: {e}")
        raise

    # 3. DB Insert (signals table)
    if signals:
        try:
            # Add session_id to each signal as it's required by table but might not be in Gemini schema output (only audio_chunk_id is)
            for sig in signals:
                sig["session_id"] = session_id
                # Ensure audio_chunk_id matches
                if sig.get("audio_chunk_id") != audio_chunk_id:
                    logger.warning(f"Gemini returned mismatched audio_chunk_id {sig.get('audio_chunk_id')}, correcting to {audio_chunk_id}")
                    sig["audio_chunk_id"] = audio_chunk_id

            data = supabase.table("signals").insert(signals).execute()
            logger.info(f"Phase 2 processing complete. Inserted {len(data.data)} signals.")
        except Exception as e:
            logger.error(f"Failed to insert signals into DB: {e}")
            raise
    else:
        logger.info("No signals extracted from this chunk.")


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
    audio_part = Part.from_uri(uri=gcs_uri, mime_type="audio/mpeg") # Assuming mp3 or similar, or generally audio/*
    
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
        logger.error(f"Error during Gemini generation: {e}")
        # Log response if available
        # if 'response' in locals():
            # logger.error(f"Response feedback: {response.prompt_feedback}")
        raise
