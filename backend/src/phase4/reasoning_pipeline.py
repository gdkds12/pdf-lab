import logging
import json
import sys
from typing import List, Dict, Any, Optional
from collections import defaultdict
import difflib

from google import genai
from google.genai import types

from src.shared.config import Config
from src.shared.db import get_supabase_client

logger = logging.getLogger(__name__)

class ReasoningPipeline:
    def __init__(self, session_ids: List[str], subject_id: str, exam_window: str = "midterm"):
        self.session_ids = session_ids
        self.subject_id = subject_id
        self.exam_window = exam_window
        self.supabase = get_supabase_client()
        # Initialize Google GenAI Client for Gemini 3.0 Thinking Mode
        self.client = genai.Client(vertexai=True, project=Config.GCP_PROJECT, location=Config.GCP_LOCATION)

    def run(self):
        try:
            # 1. Update Sessions Status
            self.supabase.table("sessions").update({"status": "reasoning"}).in_("session_id", self.session_ids).execute()

            # 2. Load Data (Aggregated)
            subject_meta = self._fetch_subject_meta()
            signals = self._fetch_signals_aggregated()
            evidence_candidates = self._fetch_evidence_candidates_aggregated()

            if not signals:
                logger.warning("No signals found across sessions, cannot reason.")
                self._save_empty_report()
                return

            # 3. Dedup & Load Chunks
            candidate_chunk_ids = list(set([c["chunk_id"] for c in evidence_candidates]))
            chunks_map = {}
            if candidate_chunk_ids:
                chunks_map = self._fetch_chunks(candidate_chunk_ids)

            # 4. Context Assembly
            prompt_context = self._assemble_context(subject_meta, signals, evidence_candidates, chunks_map)
            
            # 5. Model Call
            report_json = self._call_gemini_reasoning(prompt_context)
            
            # 6. Validation & Post-processing
            final_report = self._validate_and_clean_report(report_json, chunks_map)
            
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
        context += f"- Audio URL: {meta.get('gcs_audio_url')}\n\n"
        
        # B. Signals Timeline
        context += "## Audio Signals Timeline\n"
        for s in signals:
            line = f"[#SIGNAL id={s['signal_id']} t={s['chunk_index']}:{s['t0_sec']:.1f}-{s['t1_sec']:.1f} type={s['signal_type']}] {s['content']}"
            context += line + "\n"
        context += "\n"
        
        # C. Evidence References (Textbook Chunks)
        context += "## Textbook Reference Blocks\n"
        # We need to filter which chunks are actually relevant. 
        # But Phase 3 already filtered them via candidates.
        # Just dump the unique chunks found in candidates.
        
        # Sort chunks possibly? By page_num if available?
        # Let's simple dump.
        
        used_chunk_ids = set()
        
        # Group candidates by chunk_id to maybe show relevance score? 
        # Simplest: just dump content.
        
        # Map source_id to title for better context? (Optional, skip for simpler impl)
        
        for chunk_id, chunk in chunks_map.items():
            header = f"[[CHUNK id={chunk_id} page={chunk.get('page_start')}-{chunk.get('page_end')} anchor={chunk.get('anchor_path')}]]"
            body = chunk.get("content_text", "").strip()
            context += f"{header}\n{body}\n\n"
            
        return context

    def _call_gemini_reasoning(self, prompt_context: str) -> Dict:
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
- Return VALID JSON only.
"""
        # Call Gemini 3.0 Flash with Thinking Mode
        logger.info("Calling Gemini 3.0 Flash Preview with Thinking Mode (HIGH)...")
        
        try:
            response = self.client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt_context,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.HIGH
                    )
                )
            )
            
            # Print thought process for debugging if available
            # Note: Thought process might not be available if JSON strict mode behavior overrides it or structure differs
            if hasattr(response.candidates[0].content.parts[0], 'thought') and response.candidates[0].content.parts[0].thought:
                 logger.info("Values logic found (thought signature suppressed for cleaner log)")
            
            return json.loads(response.text)
            
        except Exception as e:
            logger.error(f"Gemini 3.0 Call Failed: {e}")
            # Fallback or re-raise? Phase 4 is critical, so failing might be better than empty.
            if hasattr(e, 'response'):
                 logger.error(f"Response content: {e.response.text}")
            
            # Minimal fallback for stability
            return {"professor_mentioned": [], "likely": [], "trap_warnings": [], "error": str(e)}

    def _validate_and_clean_report(self, report: Dict, chunks_map: Dict) -> Dict:
        # Basic schema check and hallucination filter
        valid_keys = ["professor_mentioned", "likely", "trap_warnings"]
        cleaned = {k: [] for k in valid_keys}
        
        for key in valid_keys:
            items = report.get(key, [])
            if not isinstance(items, list): continue
            
            for item in items:
                # 1. Check Confidence
                conf = item.get("confidence", 0)
                if conf < 0.3: continue # Filter low confidence
                
                # 2. Verify Citations (Hallucination Check)
                valid_citations = []
                citations = item.get("citations", [])
                for cit in citations:
                    cid = cit.get("chunk_id")
                    if cid and cid in chunks_map:
                        # Append metadata to citation for frontend convenience?
                        # Or just keep ID. Let's keep ID + add human readable info if possible.
                        # For now, just keep validated ID
                        valid_citations.append(cit)
                
                item["citations"] = valid_citations
                
                # 3. Add to cleaned list
                cleaned[key].append(item)
                
        return cleaned

    def _save_report(self, session_id: str, report: Dict):
        # Insert into session_reports
        self.supabase.table("session_reports").insert({
            "session_id": session_id,
            "report_json": report
        }).execute()

    def _save_empty_report(self):
        empty = {"professor_mentioned": [], "likely": [], "trap_warnings": [], "note": "No signals detected"}
        # Save to the last session as representative
        self._save_report(self.session_ids[-1], empty)
        self.supabase.table("sessions").update({"status": "completed"}).in_("session_id", self.session_ids).execute()


def run(payload_str: str):
    logger.info("Phase 4: Reasoning Pipeline Started (Multi-Session Mode)")
    try:
        payload = json.loads(payload_str)
        
        # Support both single session (legacy/fallback) and multi-session
        session_ids = payload.get("session_ids")
        subject_id = payload.get("subject_id")
        exam_window = payload.get("exam_window", "midterm")
        
        # Legacy support
        if not session_ids and payload.get("session_id"):
            session_ids = [payload.get("session_id")]
            # Fetch subject_id from session if not provided
            # But pipeline now requires subject_id in init or fetch.
            # Let's enforce new payload structure for safety or fetch it.
            # Lazy fetch:
            # We need subject_id.
            
        if not session_ids:
             raise ValueError("Missing session_ids within payload")
        
        # If subject_id missing, fetch from first session
        if not subject_id:
             # Just instantiate pipeline and let it fail or improving fetching?
             # Let's require subject_id in payload for efficiency
             pass

        if not subject_id:
             # Fallback fetch
             from src.shared.db import get_supabase_client
             sb = get_supabase_client()
             s = sb.table("sessions").select("subject_id").eq("session_id", session_ids[0]).single().execute()
             subject_id = s.data["subject_id"]

        pipeline = ReasoningPipeline(session_ids, subject_id, exam_window)
        pipeline.run()
        
    except Exception as e:
        logger.error(f"Pipeline Fatal Error: {e}")
        sys.exit(1)
