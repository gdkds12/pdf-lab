import logging
import json
import sys
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict

from google import genai
from google.genai import types
from jsonschema import Draft202012Validator

from src.shared.config import Config
from src.shared.db import get_supabase_client
from src.shared.validation import parse_payload, require_uuid, require_uuid_list
from src.phase3.retrieval_pipeline import RetrievalPipeline

logger = logging.getLogger(__name__)

REPORT_ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "why", "confidence", "audio_refs", "citations"],
    "properties": {
        "title": {"type": "string"},
        "why": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "audio_refs": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["audio_chunk_id", "t0_sec", "t1_sec", "signal_id"],
                "properties": {
                    "audio_chunk_id": {"type": "string"},
                    "t0_sec": {"type": "number", "minimum": 0.0},
                    "t1_sec": {"type": "number", "minimum": 0.0},
                    "signal_id": {"type": "string"}
                }
            }
        },
        "citations": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["source_id", "page_start", "page_end", "anchor_path", "chunk_id"],
                "properties": {
                    "source_id": {"type": ["string", "null"]},
                    "page_start": {"type": ["integer", "null"]},
                    "page_end": {"type": ["integer", "null"]},
                    "anchor_path": {
                        "type": ["array", "null"],
                        "items": {"type": "string"}
                    },
                    "chunk_id": {"type": "string"},
                    "reason": {"type": ["string", "null"]}
                }
            }
        }
    }
}

FINAL_REPORT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["professor_mentioned", "likely", "trap_warnings", "warnings"],
    "properties": {
        "warnings": {
            "type": "array",
            "items": {"type": "string"}
        },
        "professor_mentioned": {
            "type": "array",
            "items": REPORT_ITEM_SCHEMA
        },
        "likely": {
            "type": "array",
            "items": REPORT_ITEM_SCHEMA
        },
        "trap_warnings": {
            "type": "array",
            "items": REPORT_ITEM_SCHEMA
        }
    }
}

class ReasoningPipeline:
    def __init__(self, session_ids: List[str], subject_id: str, exam_window: str = "midterm"):
        self.session_ids = session_ids
        self.subject_id = subject_id
        self.exam_window = exam_window
        self.logs_buffer = []
        self.supabase = get_supabase_client()
        self.final_report_validator = Draft202012Validator(FINAL_REPORT_SCHEMA)
        # Initialize Google GenAI Client for Gemini 3.0 Thinking Mode
        # Use GEMINI_LOCATION (e.g. us-central1) specifically for Thinking Mode availability
        self.client = genai.Client(vertexai=True, project=Config.GCP_PROJECT, location=Config.GEMINI_LOCATION)

    def _log(self, message: str):
        logger.info(message)
        timestamp = datetime.now().isoformat()
        entry = {"ts": timestamp, "msg": message}
        self.logs_buffer.append(entry)
        try:
            # Overwrite logs column with current history
            self.supabase.table("sessions").update({
                "logs": self.logs_buffer
            }).in_("session_id", self.session_ids).execute()
        except Exception as e:
            logger.warning(f"Failed to update logs: {e}")

    def run(self):
        try:
            self._log("Starting Reasoning Phase (Phase 4)...")
            # 1. Update Sessions Status
            self.supabase.table("sessions").update({"status": "reasoning"}).in_("session_id", self.session_ids).execute()

            # 2. Load Data (Aggregated)
            self._log(f"Fetching aggregation data for {len(self.session_ids)} sessions...")
            subject_meta = self._fetch_subject_meta()
            signals = self._fetch_signals_aggregated()
            evidence_candidates = self._fetch_evidence_candidates_aggregated()

            if not signals:
                self._log("No signals found across sessions. Aborting.")
                logger.warning("No signals found across sessions, cannot reason.")
                self._save_empty_report()
                return

            # Trigger retrieval for sessions that still have no evidence.
            evidence_count_by_session: Dict[str, int] = defaultdict(int)
            for candidate in evidence_candidates:
                sid = candidate.get("session_id")
                if sid:
                    evidence_count_by_session[sid] += 1

            missing_sessions = [sid for sid in self.session_ids if evidence_count_by_session.get(sid, 0) == 0]

            if missing_sessions and signals:
                self._log(f"Missing evidence for {len(missing_sessions)} sessions. Triggering Phase 3 retrieval...")
                for sid in missing_sessions:
                    try:
                        self._log(f"Running Retrieval for session {sid}...")
                        rp = RetrievalPipeline(session_id=sid)
                        rp.run()
                    except Exception as e:
                        self._log(f"Retrieval failed for session {sid}: {e}")
                
                # Re-fetch evidence after retrieval
                evidence_candidates = self._fetch_evidence_candidates_aggregated()
                self._log(f"After retrieval: Found {len(evidence_candidates)} candidates.")

            self._log(f"Found {len(signals)} signals and {len(evidence_candidates)} evidence candidates.")

            # 3. Dedup & Load Chunks
            candidate_chunk_ids = list(set([c["chunk_id"] for c in evidence_candidates]))
            chunks_map = {}
            if candidate_chunk_ids:
                chunks_map = self._fetch_chunks(candidate_chunk_ids)
            
            self._log(f"Retrieved {len(chunks_map)} unique textbook chunks for context.")

            # 4. Context Assembly
            prompt_context = self._assemble_context(subject_meta, signals, evidence_candidates, chunks_map)
            
            # 5. Model Call
            self._log(f"Calling Gemini Thinking Mode ({Config.REASONING_MODEL_NAME}) (this may take 30-60s)...")
            report_json = self._call_gemini_reasoning(prompt_context)
            
            # 6. Validation & Post-processing
            self._log("Validating and cleaning generated report...")
            final_report = self._validate_and_clean_report(report_json, chunks_map, signals)
            if Config.PHASE4_STRICT_SCHEMA:
                self._enforce_final_report_schema(final_report)
            metrics = self._compute_phase4_metrics(final_report, signals, evidence_candidates, chunks_map)
            self._log(f"Phase4 metrics: {json.dumps(metrics, ensure_ascii=False)}")
            
            # 7. Save Report (Virtual 'All Sessions' Report)
            # Strategy: To make frontend queries simple, we save the SAME report to ALL participating sessions.
            # First, clean up any existing reports for these sessions to avoid duplicates/confusion.
            try:
                self.supabase.table("session_reports").delete().in_("session_id", self.session_ids).execute()
            except Exception as e:
                logger.warning(f"Failed to clean up old reports: {e}")

            # Then insert for all
            report_items = []
            for sid in self.session_ids:
                report_items.append({
                    "session_id": sid,
                    "report_json": final_report
                })
            
            if report_items:
                self.supabase.table("session_reports").insert(report_items).execute()
            
            # 8. Complete Sessions
            self._log("Report saved. Marking sessions as completed.")
            self.supabase.table("sessions").update({"status": "completed"}).in_("session_id", self.session_ids).execute()
            logger.info(f"Phase 4 Reasoning Succeeded for sessions: {self.session_ids}")

        except Exception as e:
            logger.error(f"Phase 4 Failed: {e}", exc_info=True)
            self.supabase.table("sessions").update({"status": "failed"}).in_("session_id", self.session_ids).execute()
            raise e

    def _fetch_subject_meta(self) -> Dict:
        subj = self.supabase.table("subjects").select("name").eq("subject_id", self.subject_id).single().execute()
        return {
            "subject_name": subj.data["name"],
            "exam_window": self.exam_window
        }

    def _fetch_signals_aggregated(self) -> List[Dict]:
        # Fetch signals for ALL sessions
        return self.supabase.table("signals")\
            .select("*")\
            .in_("session_id", self.session_ids)\
            .order("chunk_index")\
            .order("t0_sec")\
            .execute().data

    def _fetch_evidence_candidates_aggregated(self) -> List[Dict]:
        return self.supabase.table("evidence_candidates")\
            .select("*")\
            .in_("session_id", self.session_ids)\
            .execute().data

    def _fetch_chunks(self, chunk_ids: List[str]) -> Dict[str, Dict]:
        if not chunk_ids: return {}
        # Batching might be needed if really large
        res = self.supabase.table("chunks").select("*").in_("chunk_id", chunk_ids).execute()
        return {c["chunk_id"]: c for c in res.data}


    def _assemble_context(self, meta: Dict, signals: List[Dict], candidates: List[Dict], chunks_map: Dict) -> str:
        # A. Session Info
        context = f"## Exam Session Info\n"
        context += f"- Subject: {meta.get('subject_name')}\n"
        context += f"- Exam Window: {meta.get('exam_window')}\n"
        context += f"- Sessions: {len(self.session_ids)}\n\n"
        
        # B. Signals Timeline
        context += "## Audio Signals Timeline\n"
        for s in signals:
            signal_id = s.get("signal_id", "unknown")
            chunk_index = s.get("chunk_index")
            if chunk_index is None:
                chunk_index = "na"
            t0_raw = s.get("t0_sec", 0.0)
            t1_raw = s.get("t1_sec", 0.0)
            try:
                t0 = float(t0_raw if t0_raw is not None else 0.0)
            except (TypeError, ValueError):
                t0 = 0.0
            try:
                t1 = float(t1_raw if t1_raw is not None else 0.0)
            except (TypeError, ValueError):
                t1 = 0.0
            signal_type = s.get("signal_type", "likely")
            content = s.get("content", "")
            line = f"[#SIGNAL id={signal_id} t={chunk_index}:{t0:.1f}-{t1:.1f} type={signal_type}] {content}"
            context += line + "\n"
        context += "\n"
        
        # C. Evidence References (Textbook Chunks)
        context += "## Textbook Reference Blocks\n"
        # We need to filter which chunks are actually relevant. 
        # But Phase 3 already filtered them via candidates.
        # Just dump the unique chunks found in candidates.
        
        # Sort chunks possibly? By page_num if available?
        # Let's simple dump.
        
        # Group candidates by chunk_id to maybe show relevance score? 
        # Simplest: just dump content.
        
        # Map source_id to title for better context? (Optional, skip for simpler impl)
        
        for chunk_id, chunk in chunks_map.items():
            header = f"[[CHUNK id={chunk_id} page={chunk.get('page_start')}-{chunk.get('page_end')} anchor={chunk.get('anchor_path')}]]"
            body = chunk.get("content_text", "").strip()
            context += f"{header}\n{body}\n\n"
            
        return context

    def _call_gemini_reasoning(self, prompt_context: str) -> Dict:
        response_schema = {
            "type": "object",
            "properties": {
                "warnings": {"type": "array", "items": {"type": "string"}},
                "professor_mentioned": {"type": "array"},
                "likely": {"type": "array"},
                "trap_warnings": {"type": "array"}
            },
            "required": ["professor_mentioned", "likely", "trap_warnings"]
        }

        system_prompt = """
[ROLE]
You are the "Grand Master" TA for an exam preparation service.
Your goal is to synthesize audio signals (professor's speech) and textbook references to create a high-quality exam preparation report.

[INPUT]
1. Session Info: Subject and exam scope.
2. Signal Timeline: List of important signals detected in audio.
3. Reference Blocks: Textbook chunks retrieved based on signals.

[TASK]
1. Correlate audio signals with specific textbook chunks.
2. Filter out signals that are repetitive or trivial.
3. Classify remaining items into 3 categories:
   - professor_mentioned: Explicitly emphasized by professor ("This will be on the exam", "Important").
   - likely: High probability based on signal + matching textbook content.
   - trap_warnings: Specific misconceptions or tricky points mentioned.

[OUTPUT SCHEMA (JSON Only)]
{
  "professor_mentioned": [
    {
      "title": "Topic Name",
      "why": "Explanation citing audio and text",
      "confidence": 0.0-1.0,
      "audio_refs": [{"signal_id": "..."}],
      "citations": [{"chunk_id": "...", "reason": "..."}]
    }
  ],
  "likely": [...],
  "trap_warnings": [...]
}

[CONSTRAINTS]
- If a signal has NO matching textbook reference but is very explicit in audio, keep it but note "Textbook reference missing" in 'why'.
- If a Reference Block is not relevant to any signal, ignore it.
- Use EXACT chunk_ids from input in citations.
- Keep the report paraphrased. Do not copy long textbook sentences verbatim.
- Never output raw textbook passages.
- Return VALID JSON only.
- **IMPORTANT**: Write the report entirely in KOREAN (한국어). The 'title' and 'why' fields MUST be in Korean.
- **STYLE**: In the 'why' field, write natural sentences. **NEVER** include raw Signal IDs or Chunk IDs (e.g., "(id:f3c...)", "(CHUNK id=...)") in the text. Citing them in 'audio_refs' or 'citations' array is enough.
"""
        # Call Gemini 3.0 Flash with Thinking Mode
        logger.info(f"Calling {Config.REASONING_MODEL_NAME} with Thinking Mode (HIGH) [DEBUG: {Config.REASONING_MODEL_NAME}]")
        
        try:
            response = self.client.models.generate_content(
                model=Config.REASONING_MODEL_NAME,
                contents=prompt_context,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=response_schema
                )
            )
            
            # Print thought process for debugging if available
            # Note: Thought process might not be available if JSON strict mode behavior overrides it or structure differs
            if hasattr(response.candidates[0].content.parts[0], 'thought') and response.candidates[0].content.parts[0].thought:
                 logger.info("Values logic found (thought signature suppressed for cleaner log)")
            
            return json.loads(response.text)

        except Exception as e:
            logger.error(f"Gemini Call Failed: {e}")
            raise e

    def _validate_and_clean_report(self, report: Dict, chunks_map: Dict, signals: List[Dict]) -> Dict:
        # Basic schema check and hallucination filter
        valid_keys = ["professor_mentioned", "likely", "trap_warnings"]
        cleaned = {k: [] for k in valid_keys}
        warnings: List[str] = []
        signal_map = {s["signal_id"]: s for s in signals if s.get("signal_id")}
        
        # Regex to strip (id:...) or (CHUNK id=...) from text
        # Patterns: 
        # 1. (id: UUID)
        # 2. (CHUNK id=UUID)
        # 3. id:UUID (sometimes Gemini forgets parenthesis)
        # capture group 1 is the ID
        id_pattern = re.compile(r'\(?id:([\w-]+)\)?', re.IGNORECASE)
        chunk_pattern = re.compile(r'\(?CHUNK id=([\w-]+)\)?', re.IGNORECASE)

        for key in valid_keys:
            items = report.get(key, [])
            if not isinstance(items, list): continue
            
            for item in items:
                title = item.get("title")
                why = item.get("why")
                if not isinstance(title, str) or not isinstance(why, str):
                    warnings.append(f"{key}: title/why 누락으로 항목 제외")
                    continue

                raw_citations = item.get("citations", [])
                if not isinstance(raw_citations, list):
                    raw_citations = []

                found_ids = []
                found_ids.extend(id_pattern.findall(why))
                found_ids.extend(chunk_pattern.findall(why))
                why = id_pattern.sub("", why)
                why = chunk_pattern.sub("", why)

                title = " ".join(title.strip().split())[:Config.PHASE4_MAX_TITLE_LEN]
                why = " ".join(why.strip().split())[:Config.PHASE4_MAX_WHY_LEN]

                # 1. Check Confidence
                conf = item.get("confidence", 0)
                if not isinstance(conf, (int, float)) or conf < 0.3:
                    continue
                conf = float(max(0.0, min(1.0, conf)))
                
                # 2. Verify Audio References
                valid_audio_refs = []
                audio_refs = item.get("audio_refs", [])
                if isinstance(audio_refs, list):
                    for ref in audio_refs:
                        if not isinstance(ref, dict):
                            continue
                        signal_id = ref.get("signal_id")
                        signal_row = signal_map.get(signal_id)
                        if not signal_row:
                            continue

                        t0 = ref.get("t0_sec", signal_row.get("t0_sec"))
                        t1 = ref.get("t1_sec", signal_row.get("t1_sec"))
                        if not isinstance(t0, (int, float)) or not isinstance(t1, (int, float)):
                            continue
                        if t0 < 0 or t1 < 0 or t0 > t1:
                            continue

                        valid_audio_refs.append({
                            "signal_id": signal_id,
                            "audio_chunk_id": ref.get("audio_chunk_id", signal_row.get("audio_chunk_id")),
                            "t0_sec": float(t0),
                            "t1_sec": float(t1)
                        })
                valid_audio_refs = valid_audio_refs[:Config.PHASE4_MAX_AUDIO_REFS]

                # 3. Verify Citations (Hallucination Check)
                valid_citations = []
                citations = list(raw_citations)
                for fid in found_ids:
                    exists = any(isinstance(c, dict) and c.get("chunk_id") == fid for c in citations)
                    if not exists and fid in chunks_map:
                        citations.append({"chunk_id": fid, "reason": "설명 텍스트에서 참조 감지"})

                if isinstance(citations, list):
                    for cit in citations:
                        if not isinstance(cit, dict):
                            continue
                        cid = cit.get("chunk_id")
                        if cid and cid in chunks_map:
                            chunk = chunks_map[cid]
                            valid_citations.append({
                                "chunk_id": cid,
                                "reason": self._sanitize_reason(cit.get("reason"), chunks_map),
                                "source_id": chunk.get("source_id"),
                                "page_start": chunk.get("page_start"),
                                "page_end": chunk.get("page_end"),
                                "anchor_path": chunk.get("anchor_path")
                            })
                valid_citations = valid_citations[:Config.PHASE4_MAX_CITATIONS]

                if len(valid_audio_refs) == 0 or len(valid_citations) == 0:
                    warnings.append(f"{key}: 오디오/교재 근거 불충분으로 항목 제외")
                    continue

                if self._contains_verbatim_span(why, chunks_map, Config.PHASE4_VERBATIM_WINDOW):
                    why = "교재 핵심 개념 기반 요약입니다. 원문 직접 인용은 생략했습니다."
                    warnings.append(f"{key}: 원문 인용 보호 규칙 적용(요약으로 대체)")

                cleaned[key].append({
                    "title": title,
                    "why": why,
                    "confidence": conf,
                    "audio_refs": valid_audio_refs,
                    "citations": valid_citations
                })

        cleaned["warnings"] = list(dict.fromkeys(warnings))
        return cleaned

    def _contains_verbatim_span(self, text: str, chunks_map: Dict[str, Dict], window: int) -> bool:
        normalized = " ".join(text.split())
        if len(normalized) < window:
            return False
        step = max(1, window // 2)
        for i in range(0, len(normalized) - window + 1, step):
            span = normalized[i:i + window]
            if len(span.strip()) < window:
                continue
            for chunk in chunks_map.values():
                chunk_text = " ".join(str(chunk.get("content_text", "")).split())
                if span in chunk_text:
                    return True
        return False

    def _sanitize_reason(self, reason: Any, chunks_map: Dict[str, Dict]) -> Optional[str]:
        if not isinstance(reason, str):
            return None
        cleaned = " ".join(reason.strip().split())
        if not cleaned:
            return None
        if self._contains_verbatim_span(cleaned, chunks_map, Config.PHASE4_VERBATIM_WINDOW):
            return "교재 핵심 문맥과 일치"
        return cleaned[:160]

    def _enforce_final_report_schema(self, report: Dict[str, Any]):
        errors = sorted(self.final_report_validator.iter_errors(report), key=lambda err: list(err.path))
        if not errors:
            return
        first_five = []
        for err in errors[:5]:
            path = "/".join(str(p) for p in err.path) or "$"
            first_five.append(f"{path}: {err.message}")
        message = "Final report schema validation failed: " + "; ".join(first_five)
        raise ValueError(message)

    def _compute_phase4_metrics(
        self,
        report: Dict[str, Any],
        signals: List[Dict[str, Any]],
        evidence_candidates: List[Dict[str, Any]],
        chunks_map: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        categories = ["professor_mentioned", "likely", "trap_warnings"]
        item_counts = {k: len(report.get(k, [])) for k in categories}
        all_items: List[Dict[str, Any]] = []
        for key in categories:
            value = report.get(key, [])
            if isinstance(value, list):
                all_items.extend(value)

        audio_refs_total = 0
        citations_total = 0
        unique_signal_refs = set()
        unique_cited_chunks = set()
        confidence_values = []
        for item in all_items:
            conf = item.get("confidence")
            if isinstance(conf, (int, float)):
                confidence_values.append(float(conf))

            refs = item.get("audio_refs", [])
            if isinstance(refs, list):
                audio_refs_total += len(refs)
                for ref in refs:
                    if isinstance(ref, dict) and ref.get("signal_id"):
                        unique_signal_refs.add(ref["signal_id"])

            citations = item.get("citations", [])
            if isinstance(citations, list):
                citations_total += len(citations)
                for citation in citations:
                    if isinstance(citation, dict) and citation.get("chunk_id"):
                        unique_cited_chunks.add(citation["chunk_id"])

        avg_confidence = round(sum(confidence_values) / len(confidence_values), 4) if confidence_values else None
        warnings_count = len(report.get("warnings", [])) if isinstance(report.get("warnings"), list) else 0

        return {
            "input_signals": len(signals),
            "input_evidence_candidates": len(evidence_candidates),
            "input_unique_chunks": len(chunks_map),
            "output_items_total": len(all_items),
            "output_item_counts": item_counts,
            "output_audio_refs_total": audio_refs_total,
            "output_citations_total": citations_total,
            "output_unique_signal_refs": len(unique_signal_refs),
            "output_unique_cited_chunks": len(unique_cited_chunks),
            "output_avg_confidence": avg_confidence,
            "warnings_count": warnings_count
        }

    def _save_report(self, session_id: str, report: Dict):
        # Insert into session_reports
        self.supabase.table("session_reports").insert({
            "session_id": session_id,
            "report_json": report
        }).execute()

    def _save_empty_report(self):
        empty = {
            "professor_mentioned": [],
            "likely": [],
            "trap_warnings": [],
            "warnings": ["유효한 신호가 없어 리포트 항목이 생성되지 않았습니다."]
        }
        for sid in self.session_ids:
            self._save_report(sid, empty)
        self.supabase.table("sessions").update({"status": "completed"}).in_("session_id", self.session_ids).execute()


def run(payload_str: str):
    logger.info("Phase 4: Reasoning Pipeline Started (Multi-Session Mode)")
    try:
        payload = parse_payload(payload_str)
        
        # Support both single session (legacy/fallback) and multi-session
        session_ids = require_uuid_list(payload, "session_ids", fallback_key="session_id")
        subject_id = payload.get("subject_id")
        exam_window = payload.get("exam_window", "midterm")
        
        # If subject_id missing, fetch from first session
        if subject_id:
            subject_id = require_uuid(payload, "subject_id")

        if not subject_id:
             # Fallback fetch
             from src.shared.db import get_supabase_client
             sb = get_supabase_client()
             try:
                 s = sb.table("sessions").select("subject_id").eq("session_id", session_ids[0]).single().execute()
                 if not s.data or not s.data.get("subject_id"):
                     raise ValueError(f"Session not found or missing subject_id: {session_ids[0]}")
                 subject_id = s.data["subject_id"]
             except Exception as exc:
                 raise ValueError(f"Session lookup failed for session_id={session_ids[0]}") from exc

        pipeline = ReasoningPipeline(session_ids, subject_id, exam_window)
        pipeline.run()
        
    except Exception as e:
        logger.error(f"Pipeline Fatal Error: {e}")
        sys.exit(1)
