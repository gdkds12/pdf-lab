
-- Patch to add status tracking to audio_chunks
alter table audio_chunks 
add column if not exists status text not null default 'pending' 
  check (status in ('pending','processing','completed','failed')),
add column if not exists error_message text;

-- Index for fast status counting
create index if not exists audio_chunks_status_idx on audio_chunks(session_id, status);
