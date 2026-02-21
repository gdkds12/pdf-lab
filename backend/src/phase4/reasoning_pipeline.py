import logging
import json
import sys
import re
import time
import copy
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict, Counter

from google.genai import types
from jsonschema import Draft202012Validator
import json_repair

from src.shared.config import Config
from src.shared.db import get_supabase_client
from src.shared.gemini_api import get_gemini_api_client
from src.shared.validation import parse_payload, require_uuid, require_uuid_list
from src.phase3.retrieval_pipeline import RetrievalPipeline

logger = logging.getLogger(__name__)

QUEUE_ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "why", "importance", "importance_score", "study_action", "proof_refs", "references"],
    "properties": {
        "rank": {"type": "integer", "minimum": 1},
        "title": {"type": "string"},
        "problem_id": {"type": ["string", "null"]},
        "why": {"type": "string"},
        "importance": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "importance_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "study_action": {"type": "string"},
        "proof_refs": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["audio_chunk_id", "t0_sec", "t1_sec", "signal_id"],
                "properties": {
                    "audio_chunk_id": {"type": ["string", "null"]},
                    "t0_sec": {"type": "number", "minimum": 0.0},
                    "t1_sec": {"type": "number", "minimum": 0.0},
                    "signal_id": {"type": "string"},
                    "note": {"type": ["string", "null"]}
                }
            }
        },
        "references": {
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
                    "page_type": {"type": ["string", "null"]},
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
    "required": ["recommendation_queue", "warnings"],
    "properties": {
        "warnings": {
            "type": "array",
            "items": {"type": "string"}
        },
        "recommendation_queue": {
            "type": "array",
            "items": QUEUE_ITEM_SCHEMA
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
        self.client = get_gemini_api_client(shard_key=f"p4:{','.join(self.session_ids)}")

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
        previous_status_map: Dict[str, str] = {}
        try:
            self._log("Starting Reasoning Phase (Phase 4)...")

            # Snapshot current statuses so we can restore them if report generation fails.
            try:
                status_rows = self.supabase.table("sessions").select("session_id,status").in_("session_id", self.session_ids).execute().data or []
                previous_status_map = {
                    row.get("session_id"): row.get("status")
                    for row in status_rows
                    if row.get("session_id") and isinstance(row.get("status"), str)
                }
            except Exception as e:
                logger.warning(f"Failed to snapshot session statuses before phase4: {e}")

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

            # Trigger retrieval only for sessions that (1) have signals and (2) still have no evidence.
            # This prevents redundant re-execution for sessions with zero signals.
            evidence_count_by_session: Dict[str, int] = defaultdict(int)
            for candidate in evidence_candidates:
                sid = candidate.get("session_id")
                if sid:
                    evidence_count_by_session[sid] += 1

            signal_count_by_session: Dict[str, int] = defaultdict(int)
            for signal in signals:
                sid = signal.get("session_id")
                if sid:
                    signal_count_by_session[sid] += 1

            missing_sessions_with_signals = [
                sid
                for sid in self.session_ids
                if signal_count_by_session.get(sid, 0) > 0 and evidence_count_by_session.get(sid, 0) == 0
            ]
            skipped_no_signal_sessions = [
                sid
                for sid in self.session_ids
                if signal_count_by_session.get(sid, 0) == 0 and evidence_count_by_session.get(sid, 0) == 0
            ]

            if skipped_no_signal_sessions:
                self._log(
                    f"Skipping retrieval for {len(skipped_no_signal_sessions)} sessions with no signals "
                    f"(no-op sessions)."
                )

            if missing_sessions_with_signals and signals:
                self._log(
                    f"Missing evidence for {len(missing_sessions_with_signals)} sessions with signals. "
                    f"Triggering Phase 3 retrieval..."
                )
                for sid in missing_sessions_with_signals:
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
            chunks_map = self._fetch_chunks(candidate_chunk_ids) if candidate_chunk_ids else {}
            self._log(f"Retrieved {len(chunks_map)} unique textbook chunks for context.")

            # 4) Stage-style reasoning prep (Fact/Alignment/Context reduction)
            toc_sections = self._extract_toc_sections(chunks_map)
            alignment_pack = self._build_alignment_pack(signals, evidence_candidates, chunks_map)
            selected_chunk_ids = self._select_context_chunk_ids(evidence_candidates)
            self._log(
                f"Stage prep: toc={len(toc_sections)}, alignments={len(alignment_pack.get('alignments', []))}, "
                f"selected_chunks={len(selected_chunk_ids)}"
            )

            # 5. Context Assembly (reduced)
            prompt_context = self._assemble_context(
                subject_meta,
                signals,
                evidence_candidates,
                chunks_map,
                toc_sections=toc_sections,
                selected_chunk_ids=selected_chunk_ids,
            )

            # 6. Model Call (with hard budget guard)
            cost_est = self._estimate_reasoning_cost_krw(prompt_context)
            budget_krw = float(Config.PHASE4_COST_BUDGET_KRW)
            self._log(
                "Reasoning cost estimate: "
                f"input≈{int(cost_est['input_tokens_est'])} tok, "
                f"output_cap={int(cost_est['output_tokens_cap'])} tok, "
                f"est≈₩{cost_est['total_cost_krw_est']:.1f} (budget ₩{budget_krw:.1f})"
            )

            if cost_est["total_cost_krw_est"] > budget_krw:
                self._log("Skipping Gemini reasoning due to cost budget guard.")
                report_json = {
                    "warnings": [
                        (
                            "비용 가드레일로 고비용 추론을 건너뛰었습니다 "
                            f"(예상 ₩{cost_est['total_cost_krw_est']:.1f} > 한도 ₩{budget_krw:.1f})."
                        )
                    ],
                    "recommendation_queue": [],
                }
            else:
                self._log(f"Calling Gemini Thinking Mode ({Config.REASONING_MODEL_NAME}) (this may take 30-60s)...")
                report_json = self._call_gemini_reasoning(prompt_context)

            # 7. Validation & Post-processing
            self._log("Validating and cleaning generated report...")
            filtered_chunks_map = {cid: chunks_map[cid] for cid in selected_chunk_ids if cid in chunks_map}
            audio_file_name_map = self._fetch_audio_file_names([
                s.get("audio_chunk_id") for s in signals if s.get("audio_chunk_id")
            ])
            confirmed_report = self._validate_and_clean_report(
                report_json,
                filtered_chunks_map,
                signals,
                audio_file_name_map=audio_file_name_map,
            )

            # Build candidate queue fallback with concrete evidence first (signal -> top chunk),
            # then use alignment range only when evidence is missing.
            alignment_by_signal = {
                row.get("signal_id"): row for row in (alignment_pack.get("alignments") or []) if row.get("signal_id")
            }
            evidence_by_signal: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for ev in evidence_candidates:
                sid = ev.get("signal_id")
                if sid:
                    evidence_by_signal[sid].append(ev)

            candidate_rows: List[Dict[str, Any]] = []
            for s in signals:
                sid = s.get("signal_id")
                if not sid:
                    continue
                evs = sorted(
                    evidence_by_signal.get(sid, []),
                    key=lambda r: float(r.get("rrf_score") or 0.0),
                    reverse=True,
                )
                top_ev = evs[0] if evs else None
                top_chunk = chunks_map.get(top_ev.get("chunk_id")) if top_ev else None
                importance = float(s.get("importance") or 0.5)
                candidate_rows.append({
                    "signal": s,
                    "sid": sid,
                    "importance": importance,
                    "top_ev": top_ev,
                    "top_chunk": top_chunk,
                })

            candidate_rows.sort(key=lambda x: x.get("importance", 0.0), reverse=True)
            page_search_cache: Dict[str, Optional[Dict[str, Any]]] = {}
            strong_candidates: List[Dict[str, Any]] = []
            weak_candidates: List[Dict[str, Any]] = []
            for row in candidate_rows:
                s = row["signal"]
                sid = row["sid"]
                importance = row["importance"]
                top_ev = row.get("top_ev")
                top_chunk = row.get("top_chunk") or {}
                align = alignment_by_signal.get(sid) or {}

                page_start = top_chunk.get("page_start")
                page_end = top_chunk.get("page_end")
                if page_start is None:
                    page_start = align.get("pred_page_start")
                if page_end is None:
                    page_end = align.get("pred_page_end")

                resolved_chunk = dict(top_chunk) if isinstance(top_chunk, dict) else {}
                cache_key = f"{resolved_chunk.get('source_id')}|{page_start}|{page_end}|{(top_ev or {}).get('chunk_id')}"
                if cache_key not in page_search_cache:
                    page_search_cache[cache_key] = self._search_problem_chunk_near_pages(
                        source_id=resolved_chunk.get("source_id"),
                        page_start=page_start if isinstance(page_start, int) else None,
                        page_end=page_end if isinstance(page_end, int) else None,
                        seed_chunk_id=(top_ev or {}).get("chunk_id"),
                    )
                searched_chunk = page_search_cache.get(cache_key)
                if searched_chunk:
                    resolved_chunk = searched_chunk
                    page_start = resolved_chunk.get("page_start", page_start)
                    page_end = resolved_chunk.get("page_end", page_end)

                problem_obj = self._search_problem_object_near_pages(
                    source_id=resolved_chunk.get("source_id"),
                    page_start=page_start if isinstance(page_start, int) else None,
                    page_end=page_end if isinstance(page_end, int) else None,
                )

                anchor_path = resolved_chunk.get("anchor_path")
                anchor_text = None
                if isinstance(anchor_path, list) and anchor_path:
                    anchor_text = " > ".join([str(x) for x in anchor_path if x])

                title = (s.get("content") or "학습 힌트 기반 후보").strip()[:80] or "학습 힌트 기반 후보"

                reason_parts = []
                if top_ev and top_ev.get("rrf_score") is not None:
                    reason_parts.append(f"검색 점수 {float(top_ev.get('rrf_score')):.3f}")
                if page_start is not None or page_end is not None:
                    reason_parts.append(f"예상 범위 p.{page_start or '?'}-{page_end or '?'}")
                if anchor_text:
                    reason_parts.append(f"목차 {anchor_text}")
                problem_label = None
                if problem_obj:
                    problem_label = problem_obj.get("label") or problem_obj.get("title")
                if not problem_label:
                    problem_label = self._extract_problem_label(resolved_chunk)
                if not problem_label:
                    # Enforce problem-id-first policy.
                    continue
                reason_parts.append(f"추천 문제 {problem_label}")
                if searched_chunk:
                    reason_parts.append("페이지 검색으로 예제 문제 재탐색")
                if problem_obj and problem_obj.get("snippet"):
                    reason_parts.append(f"근거 {str(problem_obj.get('snippet'))[:90]}")
                reason_text = " | ".join(reason_parts) if reason_parts else "오디오 힌트 기반 후보"

                audio_chunk_id = s.get("audio_chunk_id")
                audio_file_name = audio_file_name_map.get(audio_chunk_id) if audio_chunk_id else None
                note_text = s.get("signal_type") or "hint"
                if audio_file_name:
                    note_text = f"{note_text} | 파일:{audio_file_name}"

                item = {
                    "title": title,
                    "problem_id": str(problem_label),
                    "why": reason_text,
                    "importance": importance,
                    "importance_score": int(round(importance * 100)),
                    "study_action": "해당 범위의 핵심 개념 확인 후 연습문제/예제를 우선 풀이하세요.",
                    "proof_refs": [
                        {
                            "signal_id": sid,
                            "audio_chunk_id": audio_chunk_id,
                            "t0_sec": float(s.get("t0_sec") or 0.0),
                            "t1_sec": float(s.get("t1_sec") or 0.0),
                            "note": note_text,
                        }
                    ],
                    "references": [
                        {
                            "chunk_id": resolved_chunk.get("chunk_id") or (top_ev or {}).get("chunk_id") or "pred-range",
                            "reason": f"선정 이유: {reason_text}",
                            "source_id": resolved_chunk.get("source_id"),
                            "page_start": page_start,
                            "page_end": page_end,
                            "page_type": "pdf_page",
                            "anchor_path": anchor_path,
                        }
                    ],
                }

                has_real_evidence = bool((top_ev and resolved_chunk and resolved_chunk.get("chunk_id")) or (resolved_chunk and resolved_chunk.get("chunk_id")))
                has_page = (page_start is not None) or (page_end is not None)
                if has_real_evidence and has_page:
                    strong_candidates.append(item)
                else:
                    weak_candidates.append(item)

            candidate_queue: List[Dict[str, Any]] = []
            for idx, item in enumerate((strong_candidates + weak_candidates)[: Config.PHASE4_MAX_QUEUE_ITEMS], start=1):
                item["rank"] = idx
                candidate_queue.append(item)

            confirmed_from_model = confirmed_report.get("recommendation_queue", []) or []
            confirmed_fallback = [dict(x) for x in strong_candidates[: min(8, len(strong_candidates))]]
            for idx, item in enumerate(confirmed_fallback, start=1):
                item["rank"] = idx

            min_n = max(1, int(Config.PHASE4_MIN_RECOMMENDATIONS))
            if len(candidate_queue) < min_n:
                src_ids = sorted({c.get("source_id") for c in chunks_map.values() if c.get("source_id")})
                extras = self._fetch_problem_objects_for_sources(src_ids, limit=max(0, min_n - len(candidate_queue)) + 10)
                top_signals = sorted(signals, key=lambda s: float(s.get("importance") or 0.0), reverse=True)
                for obj in extras:
                    if len(candidate_queue) >= min_n:
                        break
                    label = obj.get("label") or obj.get("title")
                    if not label:
                        continue
                    keyset = {(x.get("problem_id"), x.get("title")) for x in candidate_queue}
                    if (str(label), str(label)) in keyset:
                        continue
                    sig = top_signals[len(candidate_queue) % max(1, len(top_signals))] if top_signals else {}
                    sid = sig.get("signal_id") or "fallback-signal"
                    audio_chunk_id = sig.get("audio_chunk_id")
                    note_text = (sig.get("signal_type") or "hint")
                    if audio_chunk_id and audio_file_name_map.get(audio_chunk_id):
                        note_text += f" | 파일:{audio_file_name_map.get(audio_chunk_id)}"
                    chunk_id = obj.get("chunk_id")
                    # Hard guard: do not emit virtual references (e.g., "object-index").
                    if not isinstance(chunk_id, str) or not chunk_id:
                        continue

                    candidate_queue.append({
                        "rank": len(candidate_queue) + 1,
                        "title": str(label),
                        "problem_id": str(label),
                        "why": f"추천 문제 {label} | 교재 객체 인덱스 기반 매칭",
                        "importance": float(sig.get("importance") or 0.6),
                        "importance_score": int(round(float(sig.get("importance") or 0.6) * 100)),
                        "study_action": "해당 문제를 먼저 풀고 동일 개념의 유사 문제를 1~2개 추가로 풀이하세요.",
                        "proof_refs": [{
                            "signal_id": sid,
                            "audio_chunk_id": audio_chunk_id,
                            "t0_sec": float(sig.get("t0_sec") or 0.0),
                            "t1_sec": float(sig.get("t1_sec") or 0.0),
                            "note": note_text,
                        }],
                        "references": [{
                            "chunk_id": chunk_id,
                            "reason": f"선정 이유: {obj.get('snippet') or '교재 객체 인덱스 매칭'}",
                            "source_id": obj.get("source_id"),
                            "page_start": obj.get("page_start"),
                            "page_end": obj.get("page_end"),
                            "page_type": "pdf_page",
                            "anchor_path": obj.get("anchor_path"),
                        }],
                    })

            merged_warnings = list(dict.fromkeys((confirmed_report.get("warnings") or []) + report_json.get("warnings", [])))
            if not candidate_queue:
                merged_warnings.append("예제/연습문제 라벨이 확인된 교재 청크가 없어 추천 큐를 생성하지 못했습니다.")
            if not confirmed_from_model and confirmed_fallback:
                merged_warnings.append("모델 확정 추천이 비어 있어 근거 강한 후보를 confirmed로 승격했습니다.")

            confirmed_final = confirmed_from_model or confirmed_fallback
            final_report = {
                "warnings": merged_warnings,
                "recommendation_queue_confirmed": confirmed_final,
                "recommendation_queue_candidates": candidate_queue,
            }

            if len(confirmed_final) >= min_n:
                final_report["recommendation_queue"] = confirmed_final
            else:
                merged_queue: List[Dict[str, Any]] = []
                seen = set()
                for item in confirmed_final + candidate_queue:
                    key = (item.get("problem_id"), item.get("title"))
                    if key in seen:
                        continue
                    seen.add(key)
                    merged_queue.append(item)
                    if len(merged_queue) >= min(Config.PHASE4_MAX_QUEUE_ITEMS, max(min_n, len(confirmed_final))):
                        break
                final_report["recommendation_queue"] = merged_queue
                if len(final_report["recommendation_queue"]) < min_n:
                    final_report.setdefault("warnings", [])
                    final_report["warnings"].append(
                        f"추천 가능한 문제가 부족하여 최소 목표 {min_n}개를 채우지 못했습니다(현재 {len(final_report['recommendation_queue'])}개)."
                    )

            weak_count = max(0, len(candidate_queue) - len(strong_candidates))
            if weak_count > 0:
                final_report.setdefault("warnings", [])
                final_report["warnings"].append(f"근거 좌표가 약한 후보 {weak_count}개는 우선순위를 낮춰 배치했습니다.")

            if Config.PHASE4_STRICT_SCHEMA:
                # Keep legacy strict schema check for compatibility payload.
                self._enforce_final_report_schema({
                    "warnings": final_report.get("warnings", []),
                    "recommendation_queue": final_report.get("recommendation_queue", []),
                })

            metrics = self._compute_phase4_metrics(final_report, signals, evidence_candidates, filtered_chunks_map)
            self._log(f"Phase4 metrics: {json.dumps(metrics, ensure_ascii=False)}")

            if metrics.get("output_items_total", 0) == 0:
                final_report.setdefault("warnings", [])
                final_report["warnings"].append(
                    "추천 문제 큐 항목이 모두 검증 단계에서 제외되었습니다. 1개 녹음 파일만 사용한 경우 근거가 부족할 수 있으니 2~3개 이상 업로드 후 다시 생성해 보세요."
                )
                missing_signal_count = metrics.get("input_signals_without_evidence")
                if isinstance(missing_signal_count, int) and missing_signal_count > 0:
                    final_report["warnings"].append(
                        f"근거 후보가 없는 신호가 {missing_signal_count}개 있어 일부 항목이 제외되었습니다."
                    )
            
            # 7. Save per-session reports (strict session scoping + real chunk refs only)
            signal_session_map = {
                str(s.get("signal_id")): str(s.get("session_id"))
                for s in signals
                if s.get("signal_id") is not None and s.get("session_id") is not None
            }
            session_signals_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for s in signals:
                sid_raw = s.get("session_id")
                if sid_raw is not None:
                    session_signals_map[str(sid_raw)].append(s)

            fallback_source_ids: List[str] = []
            try:
                src_rows = (
                    self.supabase.table("sources")
                    .select("source_id")
                    .eq("subject_id", self.subject_id)
                    .limit(20)
                    .execute()
                    .data
                    or []
                )
                fallback_source_ids = [r.get("source_id") for r in src_rows if r.get("source_id")]
            except Exception:
                fallback_source_ids = []

            fallback_objects = [
                o for o in self._fetch_problem_objects_for_sources(fallback_source_ids, limit=500)
                if isinstance(o.get("chunk_id"), str) and o.get("chunk_id") and isinstance(o.get("label"), str) and o.get("label")
            ]
            if not fallback_objects:
                try:
                    rows = (
                        self.supabase.table("textbook_objects")
                        .select("*")
                        .in_("object_type", ["assessment", "example", "exercise"])
                        .limit(500)
                        .execute()
                        .data
                        or []
                    )
                    fallback_objects = [
                        o for o in rows
                        if isinstance(o.get("chunk_id"), str) and o.get("chunk_id") and isinstance(o.get("label"), str) and o.get("label")
                    ]
                except Exception:
                    fallback_objects = []

            def _item_belongs_to_session(item: Dict[str, Any], session_id: str) -> bool:
                proof_refs = item.get("proof_refs") or []
                if not proof_refs:
                    return False
                # keep item only when every proof signal belongs to target session
                for pf in proof_refs:
                    sig_id = pf.get("signal_id")
                    if not sig_id or signal_session_map.get(str(sig_id)) != session_id:
                        return False
                # references must point to real chunks
                refs = item.get("references") or []
                if not refs:
                    return False
                for ref in refs:
                    cid = ref.get("chunk_id")
                    if not isinstance(cid, str) or not cid:
                        return False
                return True

            def _session_scoped_report(session_id: str) -> Dict[str, Any]:
                confirmed = [
                    copy.deepcopy(it)
                    for it in (final_report.get("recommendation_queue_confirmed") or [])
                    if _item_belongs_to_session(it, session_id)
                ]
                candidates = [
                    copy.deepcopy(it)
                    for it in (final_report.get("recommendation_queue_candidates") or [])
                    if _item_belongs_to_session(it, session_id)
                ]

                # re-rank
                for idx, it in enumerate(confirmed, start=1):
                    it["rank"] = idx
                for idx, it in enumerate(candidates, start=1):
                    it["rank"] = idx

                # Build compatibility queue
                rec = confirmed if len(confirmed) >= min_n else (confirmed + candidates)

                # Session-scoped fallback fill: if sparse after strict filtering,
                # synthesize additional items from this session's own signals + problem objects.
                if len(rec) < min_n:
                    seen_keys = set((it.get("problem_id"), it.get("title")) for it in rec)
                    sigs = session_signals_map.get(session_id) or []
                    if not sigs:
                        try:
                            sigs = (
                                self.supabase.table("signals")
                                .select("signal_id,session_id,audio_chunk_id,t0_sec,t1_sec,signal_type,importance")
                                .eq("session_id", session_id)
                                .order("importance", desc=True)
                                .limit(50)
                                .execute()
                                .data
                                or []
                            )
                        except Exception:
                            sigs = []

                    local_objects = list(fallback_objects)
                    if not local_objects:
                        try:
                            src_rows = (
                                self.supabase.table("sources")
                                .select("source_id")
                                .eq("subject_id", self.subject_id)
                                .limit(10)
                                .execute()
                                .data
                                or []
                            )
                            src_ids = [r.get("source_id") for r in src_rows if r.get("source_id")]
                            local_objects = self._fetch_problem_objects_for_sources(src_ids, limit=500)
                        except Exception:
                            local_objects = []

                    local_objects = [
                        o for o in local_objects
                        if isinstance(o.get("chunk_id"), str) and o.get("chunk_id") and isinstance(o.get("label"), str) and o.get("label")
                    ]

                    if sigs and not local_objects:
                        try:
                            local_objects = (
                                self.supabase.table("textbook_objects")
                                .select("*")
                                .in_("object_type", ["assessment", "example", "exercise"])
                                .limit(300)
                                .execute()
                                .data
                                or []
                            )
                            local_objects = [
                                o for o in local_objects
                                if isinstance(o.get("chunk_id"), str) and o.get("chunk_id") and isinstance(o.get("label"), str) and o.get("label")
                            ]
                        except Exception:
                            local_objects = []

                    if sigs and local_objects:
                        max_fill = min(Config.PHASE4_MAX_QUEUE_ITEMS, min_n)
                        obj_idx = 0
                        while len(rec) < max_fill and obj_idx < len(local_objects):
                            obj = local_objects[obj_idx]
                            obj_idx += 1
                            label = str(obj.get("label") or "").strip()
                            if not label:
                                continue
                            key = (label, label)
                            if key in seen_keys:
                                continue
                            sig = sigs[(len(rec) + obj_idx) % len(sigs)]
                            importance = float(sig.get("importance") or 0.6)
                            rec.append({
                                "rank": len(rec) + 1,
                                "title": label,
                                "problem_id": label,
                                "why": f"추천 문제 {label} | 세션 전용 fallback 매칭",
                                "importance": importance,
                                "importance_score": int(round(importance * 100)),
                                "study_action": "해당 문제를 먼저 풀이하고 오답 원인을 정리하세요.",
                                "proof_refs": [{
                                    "signal_id": sig.get("signal_id"),
                                    "audio_chunk_id": sig.get("audio_chunk_id"),
                                    "t0_sec": float(sig.get("t0_sec") or 0.0),
                                    "t1_sec": float(sig.get("t1_sec") or 0.0),
                                    "note": str(sig.get("signal_type") or "session-fallback"),
                                }],
                                "references": [{
                                    "chunk_id": obj.get("chunk_id"),
                                    "reason": f"선정 이유: {obj.get('snippet') or '세션 전용 fallback 매칭'}",
                                    "source_id": obj.get("source_id"),
                                    "page_start": obj.get("page_start"),
                                    "page_end": obj.get("page_end"),
                                    "page_type": "pdf_page",
                                    "anchor_path": obj.get("anchor_path"),
                                }],
                            })
                            seen_keys.add(key)

                if len(rec) == 0 and sigs:
                    # Final deterministic fallback: reuse globally validated candidate references,
                    # but bind proof refs to this session's own signals.
                    g_candidates = [
                        x for x in (candidate_queue or [])
                        if (x.get("references") or [{}])[0].get("chunk_id")
                    ]
                    for j, base in enumerate(g_candidates):
                        if len(rec) >= min_n:
                            break
                        sig = sigs[j % len(sigs)]
                        ref0 = (base.get("references") or [{}])[0]
                        chunk_id = ref0.get("chunk_id")
                        if not isinstance(chunk_id, str) or not chunk_id:
                            continue
                        title = str(base.get("title") or base.get("problem_id") or "추천 문제").strip()
                        pid = str(base.get("problem_id") or title).strip()
                        importance = float(sig.get("importance") or base.get("importance") or 0.6)
                        rec.append({
                            "rank": len(rec) + 1,
                            "title": title,
                            "problem_id": pid,
                            "why": f"추천 문제 {pid} | 세션 하드 fallback",
                            "importance": importance,
                            "importance_score": int(round(importance * 100)),
                            "study_action": "문제를 먼저 풀고 풀이 근거를 확인하세요.",
                            "proof_refs": [{
                                "signal_id": sig.get("signal_id"),
                                "audio_chunk_id": sig.get("audio_chunk_id"),
                                "t0_sec": float(sig.get("t0_sec") or 0.0),
                                "t1_sec": float(sig.get("t1_sec") or 0.0),
                                "note": str(sig.get("signal_type") or "hard-fallback"),
                            }],
                            "references": [{
                                "chunk_id": chunk_id,
                                "reason": ref0.get("reason") or "선정 이유: 세션 하드 fallback",
                                "source_id": ref0.get("source_id"),
                                "page_start": ref0.get("page_start"),
                                "page_end": ref0.get("page_end"),
                                "page_type": ref0.get("page_type") or "pdf_page",
                                "anchor_path": ref0.get("anchor_path"),
                            }],
                        })

                # Final top-up to target minimum count.
                if len(rec) < min_n and sigs:
                    g_candidates = [
                        x for x in (candidate_queue or [])
                        if (x.get("references") or [{}])[0].get("chunk_id")
                    ]
                    k = 0
                    while len(rec) < min_n and g_candidates:
                        base = g_candidates[k % len(g_candidates)]
                        sig = sigs[k % len(sigs)]
                        ref0 = (base.get("references") or [{}])[0]
                        chunk_id = ref0.get("chunk_id")
                        if isinstance(chunk_id, str) and chunk_id:
                            title = str(base.get("title") or base.get("problem_id") or f"추천 문제 {len(rec)+1}")
                            pid = str(base.get("problem_id") or title)
                            rec.append({
                                "rank": len(rec) + 1,
                                "title": title,
                                "problem_id": pid,
                                "why": f"추천 문제 {pid} | 세션 보강 top-up",
                                "importance": float(sig.get("importance") or 0.6),
                                "importance_score": int(round(float(sig.get("importance") or 0.6) * 100)),
                                "study_action": "문제를 먼저 풀고 풀이 근거를 확인하세요.",
                                "proof_refs": [{
                                    "signal_id": sig.get("signal_id"),
                                    "audio_chunk_id": sig.get("audio_chunk_id"),
                                    "t0_sec": float(sig.get("t0_sec") or 0.0),
                                    "t1_sec": float(sig.get("t1_sec") or 0.0),
                                    "note": str(sig.get("signal_type") or "top-up"),
                                }],
                                "references": [{
                                    "chunk_id": chunk_id,
                                    "reason": ref0.get("reason") or "선정 이유: 세션 보강 top-up",
                                    "source_id": ref0.get("source_id"),
                                    "page_start": ref0.get("page_start"),
                                    "page_end": ref0.get("page_end"),
                                    "page_type": ref0.get("page_type") or "pdf_page",
                                    "anchor_path": ref0.get("anchor_path"),
                                }],
                            })
                        k += 1
                        if k > 1000:
                            break

                rec = rec[: Config.PHASE4_MAX_QUEUE_ITEMS]
                for idx, it in enumerate(rec, start=1):
                    it["rank"] = idx

                warnings = list(final_report.get("warnings") or [])
                if not sigs:
                    warnings.append("이 세션은 추출된 신호(signals)가 없어 추천을 생성할 수 없습니다.")
                elif len(rec) < min_n:
                    warnings.append(
                        f"세션 전용 근거 필터를 적용해 추천 수가 {len(rec)}개입니다(목표 {min_n}개)."
                    )

                return {
                    "warnings": list(dict.fromkeys(warnings)),
                    "recommendation_queue_confirmed": confirmed,
                    "recommendation_queue_candidates": candidates,
                    "recommendation_queue": rec,
                }

            try:
                self.supabase.table("session_reports").delete().in_("session_id", self.session_ids).execute()
            except Exception as e:
                logger.warning(f"Failed to clean up old reports: {e}")

            report_items = []
            for sid in self.session_ids:
                report_items.append({
                    "session_id": sid,
                    "report_json": _session_scoped_report(sid)
                })

            if report_items:
                self.supabase.table("session_reports").insert(report_items).execute()
            
            # 8. Complete Sessions
            self._log("Report saved. Marking sessions as completed.")
            self.supabase.table("sessions").update({"status": "completed"}).in_("session_id", self.session_ids).execute()
            logger.info(f"Phase 4 Reasoning Succeeded for sessions: {self.session_ids}")

        except Exception as e:
            logger.error(f"Phase 4 Failed: {e}", exc_info=True)

            # Do NOT mark all source sessions as failed when report generation fails.
            # Restore prior statuses to prevent user files/sessions from being stuck in failed.
            try:
                if previous_status_map:
                    grouped: Dict[str, List[str]] = defaultdict(list)
                    for sid in self.session_ids:
                        prev = previous_status_map.get(sid)
                        if isinstance(prev, str) and prev:
                            grouped[prev].append(sid)
                    for prev_status, ids in grouped.items():
                        self.supabase.table("sessions").update({"status": prev_status}).in_("session_id", ids).execute()
                else:
                    # Conservative fallback when snapshot is unavailable.
                    self.supabase.table("sessions").update({"status": "completed"}).in_("session_id", self.session_ids).execute()
            except Exception as restore_err:
                logger.error(f"Failed to restore session statuses after phase4 failure: {restore_err}", exc_info=True)

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
        if not chunk_ids:
            return {}

        # Avoid PostgREST URI-too-long (414) by chunking IN queries.
        batch_size = 200
        merged: Dict[str, Dict] = {}
        for i in range(0, len(chunk_ids), batch_size):
            batch = chunk_ids[i:i + batch_size]
            res = self.supabase.table("chunks").select("*").in_("chunk_id", batch).execute()
            for row in (res.data or []):
                cid = row.get("chunk_id")
                if cid:
                    merged[cid] = row
        return merged

    def _fetch_audio_file_names(self, audio_chunk_ids: List[str]) -> Dict[str, str]:
        ids = [x for x in audio_chunk_ids if isinstance(x, str) and x]
        if not ids:
            return {}

        merged: Dict[str, str] = {}
        batch_size = 200
        for i in range(0, len(ids), batch_size):
            batch = ids[i:i + batch_size]
            rows = []
            try:
                rows = self.supabase.table("audio_chunks").select("*").in_("audio_chunk_id", batch).execute().data or []
            except Exception:
                try:
                    rows = self.supabase.table("audio_chunks").select("*").in_("chunk_id", batch).execute().data or []
                except Exception:
                    rows = []

            for row in rows:
                key = row.get("audio_chunk_id") or row.get("chunk_id")
                if not key:
                    continue
                fname = (
                    row.get("original_filename")
                    or row.get("file_name")
                    or row.get("filename")
                    or row.get("storage_path")
                    or ""
                )
                if isinstance(fname, str) and fname:
                    merged[key] = fname.split("/")[-1]
        return merged

    def _extract_problem_label(self, chunk: Dict[str, Any]) -> Optional[str]:
        text = (chunk or {}).get("content_text") or ""
        if not isinstance(text, str) or not text:
            return None
        patterns = [
            r"(연습문제\s*\d+[\-\.]?\d*)",
            r"(예제\s*\d+[\-\.]?\d*)",
            r"((?:Exercise)\s*\d+[\-\.]?\d*)",
        ]
        for p in patterns:
            m = re.search(p, text, flags=re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    def _search_problem_object_near_pages(
        self,
        source_id: Optional[str],
        page_start: Optional[int],
        page_end: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        if not source_id:
            return None
        if not isinstance(page_start, int) and not isinstance(page_end, int):
            return None

        s = page_start if isinstance(page_start, int) else page_end
        e = page_end if isinstance(page_end, int) else page_start
        if s is None or e is None:
            return None

        left = max(1, min(s, e) - max(0, Config.PHASE4_PAGE_SEARCH_RADIUS))
        right = max(s, e) + max(0, Config.PHASE4_PAGE_SEARCH_RADIUS)

        try:
            rows = (
                self.supabase.table("textbook_objects")
                .select("*")
                .eq("source_id", source_id)
                .in_("object_type", ["assessment", "example", "exercise"])
                .gte("page_start", left)
                .lte("page_end", right)
                .limit(max(1, Config.PHASE4_PAGE_SEARCH_MAX_PER_SIGNAL))
                .execute()
                .data
                or []
            )
        except Exception:
            return None

        return rows[0] if rows else None

    def _fetch_problem_objects_for_sources(self, source_ids: List[str], limit: int = 30) -> List[Dict[str, Any]]:
        ids = [x for x in source_ids if isinstance(x, str) and x]
        if not ids:
            return []
        out: List[Dict[str, Any]] = []
        for sid in ids[:5]:
            try:
                rows = (
                    self.supabase.table("textbook_objects")
                    .select("*")
                    .eq("source_id", sid)
                    .in_("object_type", ["assessment", "example", "exercise"])
                    .limit(limit)
                    .execute()
                    .data
                    or []
                )
                out.extend(rows)
            except Exception:
                continue
        return out[:limit]

    def _search_problem_chunk_near_pages(
        self,
        source_id: Optional[str],
        page_start: Optional[int],
        page_end: Optional[int],
        seed_chunk_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if not source_id:
            return None
        if not isinstance(page_start, int) and not isinstance(page_end, int):
            return None

        s = page_start if isinstance(page_start, int) else page_end
        e = page_end if isinstance(page_end, int) else page_start
        if s is None or e is None:
            return None

        left = max(1, min(s, e) - max(0, Config.PHASE4_PAGE_SEARCH_RADIUS))
        right = max(s, e) + max(0, Config.PHASE4_PAGE_SEARCH_RADIUS)

        try:
            rows = (
                self.supabase.table("chunks")
                .select("*")
                .eq("source_id", source_id)
                .gte("page_start", left)
                .lte("page_end", right)
                .limit(max(1, Config.PHASE4_PAGE_SEARCH_MAX_PER_SIGNAL))
                .execute()
                .data
                or []
            )
        except Exception as e:
            logger.warning(f"Page search failed for source={source_id}, range={left}-{right}: {e}")
            return None

        best = None
        best_score = -1.0
        for row in rows:
            label = self._extract_problem_label(row)
            # Only allow example/exercise-style chunks.
            if not label:
                continue
            score = 2.0
            ps = row.get("page_start")
            if isinstance(ps, int):
                center = (left + right) / 2.0
                score += max(0.0, 1.0 - min(20.0, abs(ps - center)) / 20.0)
            if seed_chunk_id and row.get("chunk_id") == seed_chunk_id:
                score += 0.2
            if score > best_score:
                best_score = score
                best = row

        return best if best_score > 0 else None

    def _extract_toc_sections(self, chunks_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        sections: List[Dict[str, Any]] = []
        seen_titles = set()
        for chunk in chunks_map.values():
            page_start = chunk.get("page_start")
            page_end = chunk.get("page_end")
            anchor = chunk.get("anchor_path")
            title = None
            if isinstance(anchor, list) and anchor:
                title = str(anchor[0]).strip()
            if not title:
                title = f"Page {page_start}" if page_start else "Unknown Section"
            key = (title.lower(), page_start, page_end)
            if key in seen_titles:
                continue
            seen_titles.add(key)
            sections.append(
                {
                    "section_id": f"sec-{len(sections)+1}",
                    "title": title,
                    "page_start": page_start,
                    "page_end": page_end,
                }
            )
        sections.sort(key=lambda s: (s.get("page_start") is None, s.get("page_start") or 10**9))
        return sections

    def _build_alignment_pack(
        self,
        signals: List[Dict[str, Any]],
        evidence_candidates: List[Dict[str, Any]],
        chunks_map: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        by_signal: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for c in evidence_candidates:
            sid = c.get("signal_id")
            if sid:
                by_signal[sid].append(c)

        alignments: List[Dict[str, Any]] = []
        for s in signals:
            sid = s.get("signal_id")
            if not sid:
                continue
            rows = by_signal.get(sid, [])
            pages: List[int] = []
            for row in sorted(rows, key=lambda r: float(r.get("rrf_score") or 0), reverse=True)[:8]:
                chunk = chunks_map.get(row.get("chunk_id"))
                if not chunk:
                    continue
                ps = chunk.get("page_start")
                pe = chunk.get("page_end")
                if isinstance(ps, int):
                    pages.append(ps)
                if isinstance(pe, int):
                    pages.append(pe)

            if pages:
                pred_start = min(pages)
                pred_end = max(pages)
                conf = min(1.0, 0.4 + 0.1 * min(6, len(pages)))
                reasons = ["evidence page aggregation"]
            else:
                pred_start = None
                pred_end = None
                conf = 0.1
                reasons = ["no evidence candidates for signal"]

            alignments.append(
                {
                    "signal_id": sid,
                    "pred_page_start": pred_start,
                    "pred_page_end": pred_end,
                    "alignment_confidence": conf,
                    "reasons": reasons,
                }
            )

        return {"alignments": alignments}

    def _select_context_chunk_ids(self, evidence_candidates: List[Dict[str, Any]]) -> List[str]:
        score_by_chunk: Dict[str, float] = defaultdict(float)
        for row in evidence_candidates:
            cid = row.get("chunk_id")
            if not cid:
                continue
            score_by_chunk[cid] += float(row.get("rrf_score") or 0.0)
        ranked = sorted(score_by_chunk.items(), key=lambda kv: kv[1], reverse=True)
        return [cid for cid, _ in ranked[: max(1, Config.PHASE4_V2_MAX_CHUNKS)]]

    def _assemble_context(
        self,
        meta: Dict,
        signals: List[Dict],
        candidates: List[Dict],
        chunks_map: Dict,
        toc_sections: Optional[List[Dict[str, Any]]] = None,
        selected_chunk_ids: Optional[List[str]] = None,
    ) -> str:
        context = f"## Learning Session Info\n"
        context += f"- Subject: {meta.get('subject_name')}\n"
        context += f"- Exam Window Label: {meta.get('exam_window')}\n"
        context += f"- Sessions: {len(self.session_ids)}\n\n"

        if toc_sections:
            context += "## Textbook TOC (Estimated from OCR)\n"
            for sec in toc_sections[:200]:
                context += f"- [{sec.get('section_id')}] {sec.get('title')} (p.{sec.get('page_start')}-{sec.get('page_end')})\n"
            context += "\n"

        context += "## Audio Signals Timeline\n"
        for s in signals:
            signal_id = s.get("signal_id", "unknown")
            chunk_index = s.get("chunk_index") if s.get("chunk_index") is not None else "na"
            try:
                t0 = float(s.get("t0_sec") or 0.0)
            except (TypeError, ValueError):
                t0 = 0.0
            try:
                t1 = float(s.get("t1_sec") or 0.0)
            except (TypeError, ValueError):
                t1 = 0.0
            signal_type = s.get("signal_type", "hint")
            content = s.get("content", "")
            context += f"[#SIGNAL id={signal_id} t={chunk_index}:{t0:.1f}-{t1:.1f} type={signal_type}] {content}\n"
        context += "\n"

        context += "## Textbook Reference Blocks (Reduced)\n"
        if selected_chunk_ids is None:
            selected_chunk_ids = list(chunks_map.keys())

        for chunk_id in selected_chunk_ids:
            chunk = chunks_map.get(chunk_id)
            if not chunk:
                continue
            header = f"[[CHUNK id={chunk_id} page={chunk.get('page_start')}-{chunk.get('page_end')} anchor={chunk.get('anchor_path')}]]"
            body = (chunk.get("content_text") or "").strip()
            if len(body) > Config.PHASE4_V2_MAX_CHARS_PER_CHUNK:
                body = body[: Config.PHASE4_V2_MAX_CHARS_PER_CHUNK] + " ..."
            context += f"{header}\n{body}\n\n"

        return context

    def _estimate_reasoning_cost_krw(self, prompt_context: str) -> Dict[str, float]:
        # Conservative rough estimator for budget guard.
        input_tokens = max(1, int(len(prompt_context) / 3.5))
        output_tokens = max(1, int(Config.REASONING_MAX_OUTPUT_TOKENS))
        input_cost = (input_tokens / 1_000_000.0) * float(Config.REASONING_INPUT_KRW_PER_1M)
        output_cost = (output_tokens / 1_000_000.0) * float(Config.REASONING_OUTPUT_KRW_PER_1M)
        total = input_cost + output_cost
        return {
            "input_tokens_est": float(input_tokens),
            "output_tokens_cap": float(output_tokens),
            "input_cost_krw_est": float(input_cost),
            "output_cost_krw_cap": float(output_cost),
            "total_cost_krw_est": float(total),
        }

    def _call_gemini_reasoning(self, prompt_context: str) -> Dict:
        response_schema = {
            "type": "object",
            "properties": {
                "warnings": {"type": "array", "items": {"type": "string"}},
                "recommendation_queue": {
                    "type": "array",
                    "items": {"type": "object"}
                }
            },
            "required": ["recommendation_queue"]
        }

        system_prompt = """
[ROLE]
You are the "Grand Master" TA for a lecture-to-study workflow assistant.
Your goal is to convert professor hints from lecture audio into actionable textbook practice recommendations with clear evidence.

[INPUT]
1. Session Info: Subject and lecture scope.
2. Signal Timeline: Important hints detected in audio.
3. Reference Blocks: Textbook chunks retrieved based on signals.

[TASK]
1. Correlate audio signals with specific textbook chunks.
2. Build ONE prioritized recommendation queue. (Do NOT output separate categories.)
3. Each recommendation must include:
   - what to study/solve (title),
   - why it matters (why),
   - suggested study action (study_action),
   - importance (0.0~1.0),
   - proof refs from audio with timestamps,
   - textbook references.
4. Remove low-confidence or repetitive items.
5. Focus on recommendation quality, not exam prediction statements.

[OUTPUT SCHEMA (JSON Only)]
{
  "recommendation_queue": [
    {
      "title": "교재 문제/단원 식별 가능한 이름",
      "why": "추천 근거 설명 (자연어)",
      "study_action": "사용자가 바로 실행할 수 있는 학습 행동",
      "importance": 0.0-1.0,
      "proof_refs": [
        {"signal_id":"...", "audio_chunk_id":"...", "t0_sec":0.0, "t1_sec":0.0, "note":"강조/함정/반복 등"}
      ],
      "references": [
        {"chunk_id":"...", "reason":"교재 연결 근거"}
      ]
    }
  ]
}

[CONSTRAINTS]
- If a signal has NO matching textbook reference, drop it from queue and add warning.
- If a Reference Block is not relevant to any signal, ignore it.
- Use EXACT chunk_ids from input in references.
- Keep the report paraphrased. Do not copy long textbook sentences verbatim.
- Never output raw textbook passages.
- Never output "정답", "예상 문제 적중" 같은 표현.
- Return VALID JSON only.
- **IMPORTANT**: Write the report entirely in KOREAN (한국어). The 'title' and 'why' fields MUST be in Korean.
- **STYLE**: In 'why', write natural Korean sentences. Do NOT include raw IDs in sentence text.
"""
        # Call Gemini 3.0 Flash with Thinking Mode
        logger.info(f"Calling {Config.REASONING_MODEL_NAME} with Thinking Mode (HIGH) [DEBUG: {Config.REASONING_MODEL_NAME}]")
        
        max_attempts = max(1, int(Config.PHASE4_REASONING_MAX_ATTEMPTS))
        retry_base_sec = max(0.5, float(Config.PHASE4_REASONING_RETRY_BASE_SEC))

        for attempt in range(1, max_attempts + 1):
            try:
                gen_config = types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    max_output_tokens=int(Config.REASONING_MAX_OUTPUT_TOKENS),
                )

                # Prefer Flash Thinking for faster/cheaper reasoning with controllable thinking budget.
                if Config.REASONING_THINKING_BUDGET is not None:
                    try:
                        gen_config.thinking_config = types.ThinkingConfig(
                            thinking_budget=int(Config.REASONING_THINKING_BUDGET)
                        )
                    except Exception:
                        # Keep backward compatibility if SDK/model combo does not expose thinking_config.
                        pass

                response = self.client.models.generate_content(
                    model=Config.REASONING_MODEL_NAME,
                    contents=prompt_context,
                    config=gen_config,
                )

                # Print thought process for debugging if available
                # Note: Thought process might not be available if JSON strict mode behavior overrides it or structure differs
                if hasattr(response.candidates[0].content.parts[0], 'thought') and response.candidates[0].content.parts[0].thought:
                    logger.info("Values logic found (thought signature suppressed for cleaner log)")

                raw_text = (response.text or "").strip()
                if not raw_text:
                    raise ValueError("Empty response from reasoning model")

                try:
                    return json.loads(raw_text)
                except json.JSONDecodeError:
                    # Robust fallback for occasionally malformed JSON outputs.
                    return json_repair.loads(raw_text)

            except Exception as e:
                if attempt < max_attempts:
                    sleep_sec = min(8.0, retry_base_sec * (2 ** (attempt - 1)))
                    logger.warning(
                        "Gemini reasoning attempt %s/%s failed: %s. Retrying in %.1fs",
                        attempt,
                        max_attempts,
                        e,
                        sleep_sec,
                    )
                    time.sleep(sleep_sec)
                    continue

                logger.error(f"Gemini Call Failed: {e}")
                raise e

    def _validate_and_clean_report(
        self,
        report: Dict,
        chunks_map: Dict,
        signals: List[Dict],
        audio_file_name_map: Optional[Dict[str, str]] = None,
    ) -> Dict:
        # Basic schema check and hallucination filter
        cleaned_queue: List[Dict[str, Any]] = []
        warnings: List[str] = []
        dropped_counts: Counter[str] = Counter()
        audio_file_name_map = audio_file_name_map or {}
        dropped_examples: List[str] = []
        signal_map = {s["signal_id"]: s for s in signals if s.get("signal_id")}
        raw_items = self._extract_raw_queue_items(report)
        
        # Regex to strip (id:...) or (CHUNK id=...) from text
        # Patterns: 
        # 1. (id: UUID)
        # 2. (CHUNK id=UUID)
        # 3. id:UUID (sometimes Gemini forgets parenthesis)
        # capture group 1 is the ID
        id_pattern = re.compile(r'\(?id:([\w-]+)\)?', re.IGNORECASE)
        chunk_pattern = re.compile(r'\(?CHUNK id=([\w-]+)\)?', re.IGNORECASE)

        for item in raw_items:
            def _record_drop(reason: str):
                dropped_counts[reason] += 1
                if len(dropped_examples) >= 5:
                    return
                raw_title = item.get("title")
                title_preview = str(raw_title).strip() if isinstance(raw_title, str) else "(제목 없음)"
                if not title_preview:
                    title_preview = "(제목 없음)"
                if len(title_preview) > 32:
                    title_preview = title_preview[:32] + "..."
                dropped_examples.append(f"{title_preview}: {reason}")

            title = item.get("title")
            why = item.get("why")
            if not isinstance(title, str) or not isinstance(why, str):
                warnings.append("추천 항목: title/why 누락으로 제외")
                _record_drop("title/why 누락")
                continue

            raw_references = item.get("references", item.get("citations", []))
            if not isinstance(raw_references, list):
                raw_references = []

            found_ids = []
            found_ids.extend(id_pattern.findall(why))
            found_ids.extend(chunk_pattern.findall(why))
            why = id_pattern.sub("", why)
            why = chunk_pattern.sub("", why)

            title = " ".join(title.strip().split())[:Config.PHASE4_MAX_TITLE_LEN]
            why = " ".join(why.strip().split())[:Config.PHASE4_MAX_WHY_LEN]

            importance = item.get("importance", item.get("confidence", 0))
            if not isinstance(importance, (int, float)) or importance < 0.3:
                _record_drop("importance 0.3 미만")
                continue
            importance = float(max(0.0, min(1.0, importance)))
            importance_score = int(round(importance * 100))

            study_action = item.get("study_action")
            if not isinstance(study_action, str) or not study_action.strip():
                study_action = "추천된 문제를 먼저 풀이하고 근거 구간을 다시 확인하세요."
            study_action = " ".join(study_action.strip().split())[:140]

            valid_proof_refs = []
            proof_refs = item.get("proof_refs", item.get("audio_refs", []))
            if isinstance(proof_refs, list):
                for ref in proof_refs:
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

                    audio_chunk_id = ref.get("audio_chunk_id", signal_row.get("audio_chunk_id"))
                    base_note = self._sanitize_reason(ref.get("note") or ref.get("reason"), chunks_map)
                    file_name = audio_file_name_map.get(audio_chunk_id) if isinstance(audio_chunk_id, str) else None
                    if file_name:
                        base_note = ((base_note + " | ") if base_note else "") + f"파일:{file_name}"

                    valid_proof_refs.append({
                        "signal_id": signal_id,
                        "audio_chunk_id": audio_chunk_id,
                        "t0_sec": float(t0),
                        "t1_sec": float(t1),
                        "note": base_note
                    })
            valid_proof_refs = valid_proof_refs[:Config.PHASE4_MAX_AUDIO_REFS]

            valid_references = []
            references = list(raw_references)
            for fid in found_ids:
                exists = any(isinstance(c, dict) and c.get("chunk_id") == fid for c in references)
                if not exists and fid in chunks_map:
                    references.append({"chunk_id": fid, "reason": "설명 텍스트에서 참조 감지"})

            if isinstance(references, list):
                for ref in references:
                    if not isinstance(ref, dict):
                        continue
                    cid = ref.get("chunk_id")
                    if cid and cid in chunks_map:
                        chunk = chunks_map[cid]
                        reason_text = self._sanitize_reason(ref.get("reason"), chunks_map)
                        problem_label = self._extract_problem_label(chunk)
                        if problem_label:
                            reason_text = ((reason_text + " | ") if reason_text else "") + f"추천 문제 {problem_label}"

                        valid_references.append({
                            "chunk_id": cid,
                            "reason": reason_text,
                            "source_id": chunk.get("source_id"),
                            "page_start": chunk.get("page_start"),
                            "page_end": chunk.get("page_end"),
                            "page_type": "pdf_page",
                            "anchor_path": chunk.get("anchor_path")
                        })
            valid_references = valid_references[:Config.PHASE4_MAX_CITATIONS]

            if len(valid_proof_refs) == 0 or len(valid_references) == 0:
                warnings.append("추천 항목: 오디오/교재 근거 불충분으로 제외")
                if len(valid_proof_refs) == 0 and len(valid_references) == 0:
                    _record_drop("오디오/교재 근거 모두 부족")
                elif len(valid_proof_refs) == 0:
                    _record_drop("오디오 근거 부족")
                else:
                    _record_drop("교재 근거 부족")
                continue

            if self._contains_verbatim_span(why, chunks_map, Config.PHASE4_VERBATIM_WINDOW):
                why = "교재 핵심 개념 기반 요약입니다. 원문 직접 인용은 생략했습니다."
                warnings.append("추천 항목: 원문 인용 보호 규칙 적용(요약으로 대체)")

            cleaned_queue.append({
                "title": title,
                "problem_id": (item.get("problem_id") if isinstance(item.get("problem_id"), str) else None),
                "why": why,
                "importance": importance,
                "importance_score": importance_score,
                "study_action": study_action,
                "proof_refs": valid_proof_refs,
                "references": valid_references
            })

        cleaned_queue = self._dedup_and_sort_queue(cleaned_queue)

        if dropped_counts:
            total_dropped = sum(dropped_counts.values())
            summary = ", ".join([f"{reason} {count}개" for reason, count in dropped_counts.items()])
            warnings.append(f"검증 제외 항목: 총 {total_dropped}개")
            warnings.append(f"검증 제외 사유: {summary}")
            if dropped_examples:
                warnings.append("검증 제외 예시: " + " | ".join(dropped_examples))

        return {
            "recommendation_queue": cleaned_queue,
            "warnings": list(dict.fromkeys(warnings))
        }

    def _extract_raw_queue_items(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        queue = report.get("recommendation_queue")
        if isinstance(queue, list):
            return [item for item in queue if isinstance(item, dict)]

        # Legacy compatibility: previous schema categories
        legacy_items: List[Dict[str, Any]] = []
        for key in ["professor_mentioned", "likely", "trap_warnings"]:
            value = report.get(key, [])
            if not isinstance(value, list):
                continue
            for item in value:
                if not isinstance(item, dict):
                    continue
                copied = dict(item)
                if not isinstance(copied.get("study_action"), str):
                    if key == "trap_warnings":
                        copied["study_action"] = "함정 포인트를 오답노트로 정리하고 유사 문제를 다시 풀어보세요."
                    elif key == "professor_mentioned":
                        copied["study_action"] = "교수 강조 구간과 연결된 교재 문제를 우선 풀이하세요."
                    else:
                        copied["study_action"] = "핵심 개념 확인 후 연습문제를 순서대로 풀이하세요."
                legacy_items.append(copied)
        return legacy_items

    def _dedup_and_sort_queue(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not items:
            return []

        merged: Dict[Any, Dict[str, Any]] = {}
        for item in items:
            title = str(item.get("title", "")).strip().lower()
            title = re.sub(r"\s+", " ", title)
            chunk_ids = sorted(
                [
                    ref.get("chunk_id")
                    for ref in item.get("references", [])
                    if isinstance(ref, dict) and ref.get("chunk_id")
                ]
            )
            key = (title, tuple(chunk_ids[:3]))
            existing = merged.get(key)
            if not existing or item.get("importance", 0.0) > existing.get("importance", 0.0):
                merged[key] = item

        deduped = list(merged.values())
        deduped.sort(
            key=lambda row: (
                row.get("importance", 0.0),
                len(row.get("proof_refs", [])),
                len(row.get("references", []))
            ),
            reverse=True
        )

        deduped = deduped[:Config.PHASE4_MAX_QUEUE_ITEMS]
        for idx, item in enumerate(deduped, start=1):
            item["rank"] = idx
        return deduped

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
        recommendation_queue = report.get("recommendation_queue", [])
        if not isinstance(recommendation_queue, list):
            recommendation_queue = []

        confirmed_queue = report.get("recommendation_queue_confirmed", [])
        if not isinstance(confirmed_queue, list):
            confirmed_queue = []

        candidate_queue = report.get("recommendation_queue_candidates", [])
        if not isinstance(candidate_queue, list):
            candidate_queue = []

        item_counts = {
            "recommendation_queue": len(recommendation_queue),
            "confirmed": len(confirmed_queue),
            "candidates": len(candidate_queue),
        }
        all_items: List[Dict[str, Any]] = []
        input_signal_ids = set()
        all_items.extend(recommendation_queue)
        for signal in signals:
            sid = signal.get("signal_id")
            if sid:
                input_signal_ids.add(sid)

        evidence_signal_ids = set()
        for candidate in evidence_candidates:
            sid = candidate.get("signal_id")
            if sid:
                evidence_signal_ids.add(sid)

        proof_refs_total = 0
        references_total = 0
        unique_signal_refs = set()
        unique_referenced_chunks = set()
        importance_values = []
        for item in all_items:
            importance = item.get("importance")
            if isinstance(importance, (int, float)):
                importance_values.append(float(importance))

            refs = item.get("proof_refs", [])
            if isinstance(refs, list):
                proof_refs_total += len(refs)
                for ref in refs:
                    if isinstance(ref, dict) and ref.get("signal_id"):
                        unique_signal_refs.add(ref["signal_id"])

            references = item.get("references", [])
            if isinstance(references, list):
                references_total += len(references)
                for reference in references:
                    if isinstance(reference, dict) and reference.get("chunk_id"):
                        unique_referenced_chunks.add(reference["chunk_id"])

        avg_importance = round(sum(importance_values) / len(importance_values), 4) if importance_values else None
        warnings_count = len(report.get("warnings", [])) if isinstance(report.get("warnings"), list) else 0

        return {
            "input_signals": len(signals),
            "input_signals_with_evidence": len(input_signal_ids & evidence_signal_ids),
            "input_signals_without_evidence": len(input_signal_ids - evidence_signal_ids),
            "input_evidence_candidates": len(evidence_candidates),
            "input_unique_chunks": len(chunks_map),
            "output_items_total": len(all_items),
            "output_item_counts": item_counts,
            "output_proof_refs_total": proof_refs_total,
            "output_references_total": references_total,
            "output_unique_signal_refs": len(unique_signal_refs),
            "output_unique_referenced_chunks": len(unique_referenced_chunks),
            "output_avg_importance": avg_importance,
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
            "recommendation_queue": [],
            "warnings": ["유효한 신호가 없어 추천 문제 큐가 생성되지 않았습니다."]
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
