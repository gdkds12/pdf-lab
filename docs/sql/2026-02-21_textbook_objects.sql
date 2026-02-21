-- textbook_objects: OCR 경량 추출(목차/문제/전략/요약) 저장용
create table if not exists public.textbook_objects (
  object_id uuid primary key default gen_random_uuid(),
  source_id uuid not null,
  chunk_id uuid null,
  object_type text not null,
  label text null,
  title text null,
  snippet text null,
  page_start int null,
  page_end int null,
  anchor_path text[] null,
  created_at timestamptz not null default now()
);

create index if not exists idx_textbook_objects_source_page
  on public.textbook_objects(source_id, page_start, page_end);

create index if not exists idx_textbook_objects_type
  on public.textbook_objects(object_type);
