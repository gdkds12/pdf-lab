
-- Patch to add status tracking to audio_chunks
-- 분리된 구문으로 실행 안정성 확보
ALTER TABLE audio_chunks ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'pending';

-- 제약조건이 없을 경우에만 충돌 없이 추가하기 위해 DROP 후 ADD (또는 DO 블록 사용 가능하나 단순화)
ALTER TABLE audio_chunks DROP CONSTRAINT IF EXISTS audio_chunks_status_check;
ALTER TABLE audio_chunks ADD CONSTRAINT audio_chunks_status_check CHECK (status IN ('pending', 'processing', 'completed', 'failed'));

ALTER TABLE audio_chunks ADD COLUMN IF NOT EXISTS error_message text;

-- Index for fast status counting
CREATE INDEX IF NOT EXISTS audio_chunks_status_idx ON audio_chunks(session_id, status);
