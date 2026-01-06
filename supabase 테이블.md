begin;

-- ------------------------------------------------------------
-- Extensions (safe to run multiple times)
-- ------------------------------------------------------------
create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";
create extension if not exists "vector";
create extension if not exists "pg_trgm";

-- ------------------------------------------------------------
-- DROP (legacy + current). CASCADE to remove dependent objects.
-- ------------------------------------------------------------
drop table if exists session_reports cascade;
drop table if exists evidence_candidates cascade;

-- legacy (v2 style) tables that might exist
drop table if exists evidencepacks cascade;
drop table if exists audiochunks cascade;

-- current/core tables
drop table if exists signals cascade;
drop table if exists audio_chunks cascade;
drop table if exists chunks cascade;
drop table if exists sessions cascade;
drop table if exists sources cascade;
drop table if exists subjects cascade;

-- ------------------------------------------------------------
-- CREATE TABLES
-- ------------------------------------------------------------

-- 1) subjects
create table subjects (
  subject_id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  name text not null,
  created_at timestamptz not null default now()
);

create index subjects_user_id_idx
on subjects(user_id);

-- 2) sources (PDFs: textbook/note)
create table sources (
  source_id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  subject_id uuid not null references subjects(subject_id) on delete cascade,

  kind text not null check (kind in ('textbook','note')),
  title text not null,

  active boolean not null default true,
  ingest_status text not null default 'queued' check (ingest_status in ('queued','running','succeeded','failed')),

  gcs_pdf_url text,
  page_count int,

  created_at timestamptz not null default now()
);

create index sources_subject_id_idx
on sources(subject_id);

create index sources_active_idx
on sources(subject_id, active);

-- 3) sessions (audio analysis session)
create table sessions (
  session_id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  subject_id uuid not null references subjects(subject_id) on delete cascade,

  exam_window text not null check (exam_window in ('midterm','final','custom')),
  gcs_audio_url text not null,

  -- optional scope selector (pages/anchors etc.)
  source_scope jsonb,

  status text not null default 'queued'
    check (status in ('queued','splitting','extracting','gathering','reasoning','completed','failed')),

  created_at timestamptz not null default now()
);

create index sessions_subject_exam_idx
on sessions(subject_id, exam_window);

-- 4) audio_chunks (recommended)
create table audio_chunks (
  chunk_id uuid primary key default gen_random_uuid(),
  session_id uuid not null references sessions(session_id) on delete cascade,

  chunk_index int not null,
  gcs_chunk_url text not null,

  -- original-audio absolute offset for this chunk
  start_offset_sec double precision not null default 0,
  duration_sec double precision,

  created_at timestamptz not null default now(),

  unique(session_id, chunk_index)
);

create index audio_chunks_session_timeline_idx
on audio_chunks(session_id, chunk_index);

-- 5) chunks (knowledge base)
-- NOTE: halfvec requires pgvector version that supports halfvec; otherwise change to vector(768).
create table chunks (
  chunk_id uuid primary key default gen_random_uuid(),
  source_id uuid not null references sources(source_id) on delete cascade,

  content_text text not null,
  embedding halfvec(768),

  page_start int,
  page_end int,
  anchor_path text[],

  content_hash text,
  token_count int,

  created_at timestamptz not null default now()
);

-- Vector index (HNSW) for halfvec cosine distance
create index chunks_embedding_hnsw
on chunks using hnsw (embedding halfvec_cosine_ops);

-- Keyword index (pg_trgm)
create index chunks_content_trgm
on chunks using gin (content_text gin_trgm_ops);

-- Optional idempotency / dedup guard
create unique index chunks_source_hash_uniq
on chunks(source_id, content_hash)
where content_hash is not null;

create index chunks_source_pages_idx
on chunks(source_id, page_start, page_end);

-- 6) signals (Phase 2 output)
create table signals (
  signal_id uuid primary key default gen_random_uuid(),
  session_id uuid not null references sessions(session_id) on delete cascade,

  audio_chunk_id uuid not null references audio_chunks(chunk_id) on delete cascade,

  chunk_index int, -- timeline helper
  signal_type text check (signal_type in ('hint','likely','trap')),

  content text not null,
  search_queries text[] not null default '{}',

  -- relative to audio_chunk
  t0_sec double precision not null,
  t1_sec double precision not null,

  importance double precision check (importance is null or (importance >= 0 and importance <= 1)),

  created_at timestamptz not null default now(),

  check (t0_sec <= t1_sec)
);

create index signals_session_timeline_idx
on signals(session_id, chunk_index, t0_sec);

create index signals_audio_chunk_idx
on signals(audio_chunk_id);

-- 7) evidence_candidates (Phase 3 output)
create table evidence_candidates (
  candidate_id uuid primary key default gen_random_uuid(),

  session_id uuid not null references sessions(session_id) on delete cascade,
  signal_id uuid references signals(signal_id) on delete cascade,

  chunk_id uuid not null references chunks(chunk_id) on delete cascade,

  query_used text,
  retrieval_channel text check (retrieval_channel in ('vector','keyword','rrf')),

  rank_vector int,
  rank_keyword int,

  score_vector double precision,
  score_keyword double precision,
  rrf_score double precision,

  created_at timestamptz not null default now()
);

create index evidence_candidates_session_chunk_idx
on evidence_candidates(session_id, chunk_id);

create index evidence_candidates_session_signal_idx
on evidence_candidates(session_id, signal_id);

create index evidence_candidates_session_rrf_idx
on evidence_candidates(session_id, rrf_score desc);

-- 8) session_reports (Phase 4 output)
create table session_reports (
  report_id uuid primary key default gen_random_uuid(),
  session_id uuid not null references sessions(session_id) on delete cascade,

  report_json jsonb not null,

  created_at timestamptz not null default now()
);

create index session_reports_session_id_idx
on session_reports(session_id);

commit;
