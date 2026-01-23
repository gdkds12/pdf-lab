# Project Thunder AI Coding Instructions

You are an expert developer working on **Project Thunder**, an AI-powered exam prediction system. This project follows a strict **Map-Reduce Architecture** across four distinct phases.

## 🏗 Big Picture Architecture
The system is divided into four main pipelines (Phases) to process textbook PDFs and lecture audio into an "Evidence-based Exam Report."

1.  **Phase 1 (Ingest)**: Processes textbook PDFs (Digital/Scanned) -> OCR -> Chunking -> Embedding (`gemini-embedding-001`) -> Supabase (`chunks` table).
2.  **Phase 2 (Audio Mapper)**: Splits audio into 30min chunks -> Gemini (`gemini-2.5-flash-lite`) -> Extracts "signals" (hints, traps) and "search queries" -> Supabase (`signals` table).
3.  **Phase 3 (Gatherer)**: Takes signals -> Hybrid Search (Vector + Keyword via RRF) -> Supabase (`evidence_candidates` table).
4.  **Phase 4 (Reducer)**: Aggregates signals + evidence -> Gemini Thinking Mode (`gemini-2.5-flash-lite`) -> Global reasoning -> Final Report (`session_reports` table).

## 🛠 Tech Stack & Conventions
-   **Backend**: Python, FastAPI (internal trigger), Google Cloud Run Jobs, Vertex AI (Gemini).
-   **Database**: Supabase (PostgreSQL 15) with `pgvector` (`halfvec(768)`) and `pg_trgm`.
-   **Frontend**: Next.js 15 (App Router), Tailwind CSS, Supabase SSR.
-   **Infrastructure**: Terraform (GCP), GCS for file storage.

## 📋 Critical Developer Workflows
-   **Database Changes**: Schema is defined in `supabase 테이블.md` and patches in `backend/src/phase2/patch_status.sql`. Always use migrations/patches when changing schema.
-   **Hybrid Search**: Controlled by the `hybrid_search_rrf` RPC in Supabase. See `backend/src/phase3/hybrid_search_rpc.sql`.
-   **Cloud Run Jobs**: Triggered via `JobsClient` in Next.js Server Actions ([web/app/dashboard/[id]/actions.ts](web/app/dashboard/[id]/actions.ts)).
-   **Prompts**: Follow the "Prompt EN, Output KO" policy. Prompts are in [프롬프트 지침.md](프롬프트 지침.md).

## 💡 Implementation Patterns
-   **Map-Reduce Principle**: Never allow Phase 2 or 3 to make final decisions. They must defer all reasoning to Phase 4.
-   **No Evidence, No Output**: All report items must link to both `audio_refs` and `citations`.
-   **Error Handling**: Use the `status` and `error_message` columns in `audio_chunks`, `sources`, and `sessions` to report progress to the UI.
-   **Context Assembly**: In Phase 4, use the structured header format for blocks: `[[CHUNK chunk_id=... source_id=... page=...]]`.

## 📂 Key Files
-   [backend/src/shared/config.py](backend/src/shared/config.py): Central configuration.
-   [backend/src/phase4/reasoning_pipeline.py](backend/src/phase4/reasoning_pipeline.py): The core "Brain" of the project.
-   [web/app/dashboard/[id]/actions.ts](web/app/dashboard/[id]/actions.ts): Integration point between Frontend and Backend jobs.
