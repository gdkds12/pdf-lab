# MVP Improvement Status

Last updated: 2026-02-17

## Scope
- Keep current server-side architecture (`Phase 1 -> 4`) as-is.
- Improve phase-to-phase reliability first.
- Strengthen copyright-defense guardrails before multi-agent rollout.

## Completed
1. Phase 2 validation hardening
- Server-side signal validation added before DB insert.
- Invalid signal rows are dropped safely.
- `chunk_index` is now propagated into `signals`.

2. Phase 2 status flow stabilization
- Chunk processing now returns success/fail counts.
- Session becomes `failed` when all chunks fail.
- Session advances to `reasoning` when at least one chunk succeeds.

3. Phase 3 runtime control
- Retrieval worker concurrency is now configurable via `PHASE3_MAX_WORKERS`.
- Query normalization for dedup was strengthened (lowercase + whitespace normalization + length checks).

4. Phase 4 evidence/link reliability
- Retrieval auto-trigger now runs only for sessions missing evidence.
- Context assembly is resilient to legacy rows missing `chunk_index` / malformed times.

5. Phase 4 output guardrails
- Model output now uses response schema.
- Server-side cleaning now enforces:
  - valid confidence,
  - valid `audio_refs` linked to real `signal_id`,
  - valid `citations` linked to real `chunk_id`.
- Evidence-incomplete items are removed.
- Validation warnings are saved into `report_json.warnings`.
- Save-time strict schema gate added (`jsonschema` validator, configurable).

6. Copyright-defense controls
- Optional source asset deletion after successful processing:
  - PDF ingest success -> source PDF delete (optional)
  - Audio extraction success -> source audio delete (optional)
- Report text/citation reason now applies paraphrase guard when verbatim spans are detected.
- Item-level caps added:
  - `PHASE4_MAX_AUDIO_REFS`
  - `PHASE4_MAX_CITATIONS`

7. UI visibility improvements
- Report modal now displays backend warnings (`검증/보호 안내`) for dropped/guarded items.

8. User-action safety improvements
- `createReportJob` now validates selected sessions are ready (`reasoning` or `completed`).
- Deleting source/session now also attempts GCS asset cleanup.

9. Retry UX improvements
- One-click retry added for failed PDF/audio items from dashboard.
- Retry flow resets the failed row and re-triggers the original phase job.

10. Phase 4 observability improvements
- Phase 4 quality metrics now logged per run:
  - input signals/candidates/chunks
  - output items, refs, citations
  - average confidence
  - warnings count

11. Retention operations baseline
- Added purge script: `backend/scripts/purge_retention_data.py`
- Supports dry-run and per-table retention windows via env vars.

12. Cross-phase payload contract hardening
- Added shared validator module: `backend/src/shared/validation.py`
- Enforced early payload validation for:
  - Phase 1 (`source_id`, `gcs_pdf_url`)
  - Phase 2 split (`session_id`, `gcs_audio_url`)
  - Phase 2 chunk (`session_id`, `audio_chunk_id`, `gcs_chunk_url`)
  - Phase 3 (`session_id`)
  - Phase 4 (`session_ids` / `session_id`, optional `subject_id`)
- Invalid UUID/GCS payloads now fail fast with explicit errors before DB query.

13. Runtime dependency compatibility fix
- Pinned `jsonschema>=4.18.0` to guarantee `Draft202012Validator` availability.
- Eliminates startup failure caused by older `jsonschema` runtime.

14. Cloud deployment verification
- Built and pushed latest backend image via Cloud Build.
- Updated `thunder-worker` job to the latest image.
- Verified on Cloud Run execution logs that new Phase 4 UUID validation is active (`Invalid UUID in session_ids`).

15. Phase 4 session lookup error clarity
- When `subject_id` is omitted and fallback lookup finds no session, error is now:
  - `Session lookup failed for session_id=...`
- This replaces low-level PostgREST internal error strings (`PGRST116`) in job logs.

## New Environment Variables
- `PHASE3_MAX_WORKERS`
- `DELETE_SOURCE_ASSETS_ON_SUCCESS`
- `PHASE4_VERBATIM_WINDOW`
- `PHASE4_MAX_TITLE_LEN`
- `PHASE4_MAX_WHY_LEN`
- `PHASE4_MAX_AUDIO_REFS`
- `PHASE4_MAX_CITATIONS`
- `PHASE4_STRICT_SCHEMA`
- `RETENTION_DRY_RUN`
- `RETENTION_SESSION_DAYS`
- `RETENTION_SOURCE_DAYS`
- `RETENTION_REPORT_DAYS`

## Remaining Before Multi-Agent
1. Wire retention purge script into scheduler/cron and confirm policy values with legal guidance.
2. Freeze a small eval set and track:
- schema pass rate,
- evidence-valid rate,
- warning rate,
- average run time/cost.
3. Upgrade runtime baseline to Python 3.11+ to avoid upcoming Google SDK support sunset warnings.

## Rollout Notes
- Recommended first production setting:
  - `DELETE_SOURCE_ASSETS_ON_SUCCESS=false` for first live soak.
- After stability confirmation:
  - switch to `true` for stricter copyright posture.
