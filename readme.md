```markdown
# Project Thunder 기술 백서 v3.0 (SSOT)
## "Map-Reduce Architecture: Global Context Reasoning for Exam Prediction" [file:1]

> 본 문서는 **Project Thunder v3.0**의 구현/운영을 위한 SSOT(Single Source of Truth)이며, 모든 구현 코드는 본 문서의 아키텍처/데이터 모델/프로토콜을 준수한다. [file:1]

---

## 변경 이력(요약)
- v3.0 핵심: Phase 2~3(Map)에서 “신호 + 근거 후보”를 최대한 수집하고, Phase 4(Reduce)에서 Long Context 기반으로 한 번에 통합 추론하여 최종 Exam Report를 생성한다. [file:1]
- 추적성/운영 보강:
  - `signals.audio_chunk_id` FK + NOT NULL(오디오 재생/감사/조인 안정성).
  - `evidence_candidates.session_id` FK(세션 삭제 시 자동 정리).
  - `evidence_candidates.signal_id` FK(“어떤 신호가 어떤 후보를 만들었는지” 추적).
  - `evidence_candidates`에 hybrid 채널/랭크/점수 메타(`rank_*`, `score_*`, `rrf_score`) 저장.
  - Phase 4 References 입력을 “텍스트 뭉치”가 아니라 “메타 포함 블록”으로 전달하여 citations 매핑 안정화.

---

## 1. 서론(Introduction)
### 1.1 프로젝트 정의 및 목표
**Project Thunder**는 대학 강의 오디오(Audio)와 전공 서적(PDF)을 통합 분석하여, **근거 기반 시험 예측 리포트(Evidence-based Exam Report)**를 자동 생성하는 AI 시스템이다. [file:1]  
본 프로젝트의 핵심 목표는 단편적인 정보 검색(Retrieval)을 넘어, 한 학기 강의 전체의 맥락(Global Context)을 이해하고 교수의 발언과 교재의 내용을 유기적으로 연결해 “시험에 나올 문제만 정리된 단권화 노트”를 제공하는 것이다. [file:1]

### 1.2 최종 산출물(Exam Report)
최종 결과물은 아래 3개 카테고리로 분류된 JSON 리포트다. [file:1]

- **professor_mentioned**: “이거 시험에 낸다” 등 교수의 명시적 예고 기반 항목. [file:1]
- **likely**: 반복 설명/강조/비중/연계로 추론된 출제 유력 항목. [file:1]
- **trap_warnings**: 교재 정의와 교수 설명 불일치, 예외 조건, 오답 유도 가능성이 있는 항목. [file:1]

**강제 규칙(SSOT):** 모든 항목은 반드시 “오디오 근거 + 교재 근거”를 포함해야 하며, 근거 매핑이 불가능하면 리포트에서 제외한다. [file:1]

---

## 2. 아키텍처 철학
### 2.1 Map-Reduce & Global Reasoning
기존 RAG의 한계인 “파편화된 정보 처리”를 극복하기 위해 **Map-Reduce** 아키텍처를 도입한다. [file:1]

- **Map (Phase 2 & 3)**: 판단을 유보하고(Decision deferral) 신호와 근거 후보를 최대한 확보하는 단계(Recall 우선). [file:1]
- **Reduce (Phase 4)**: 수집된 신호/근거를 통합하여 Long Context 입력을 구성하고, 중복 제거/인과 연결/검증을 수행해 최종 판정을 내리는 단계. [file:1]

### 2.2 단계별 책임 분리(원칙)
- Phase 2는 “신호(signal) + 검색 의도(search_queries)”만 생성하며 최종 결론을 내리지 않는다. [file:1]
- Phase 3는 “근거 후보(evidence_candidates)”를 최대한 모으고, 중복 저장을 허용한다(엄격 검증 금지). [file:1]
- Phase 4만 최종 분류/검증/리포트 작성 권한을 가진다. [file:1]

---

## 3. 인프라스트럭처 전략(Infrastructure)
### 3.1 비용 전략
고정 비용은 **OCI(무료)**로, 연산 비용은 **GCP(종량제)**로 구성하여 성능과 비용 효율을 극대화한다. [file:1]

### 3.2 OCI Ampere A1 (The Memory Bank)
- Role: 메인 데이터베이스 & 상태 저장소. [file:1]
- Spec: 4 vCPU, **24GB RAM**, 200GB Block Storage. [file:1]
- Software: Self-hosted Supabase (PostgreSQL 15+). [file:1]
- Key Tech:
  - `pgvector`: 대규모 임베딩 벡터 검색. [file:1]
  - `halfvec`: 16-bit 기반 벡터 저장으로 메모리 효율을 높이는 전략. [file:1]

**인프라 체크리스트(필수):**
- `halfvec`를 사용하므로 pgvector 확장 버전/호환성 요구사항을 운영 문서에 고정한다.

### 3.3 GCP Cloud Run & Vertex AI (The Brains)
- Compute: Cloud Run Jobs(작업이 있을 때만 컨테이너 기동). [file:1]
- AI Models:
  - `Gemini 2.5 Flash-Lite`: 오디오/비전 처리 및 Long Context 추론. [file:1]
  - Vertex AI Embeddings: `text-embedding-004` (768차원). [file:1]

---

## 4. 데이터 모델링(Database Schema)
> 아래 테이블은 v3.0 파이프라인의 데이터 흐름과 “추적 가능성(감사/디버깅)”을 동시에 만족하는 SSOT 스키마이다.

### 4.1 교재 지식 베이스: `chunks` (Phase 1)
교재 내용을 검색 가능한 형태로 저장한다. [file:1]

```sql
CREATE TABLE chunks (
  chunk_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  source_id UUID NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,

  -- 검색 데이터
  content_text TEXT NOT NULL,     -- 키워드 검색용
  embedding halfvec(768),         -- 의미 검색용

  -- 구조 정보
  page_start INT,
  page_end INT,
  anchor_path TEXT[],             -- 예: ['Chapter 1', 'Section 1.2']

  -- 운영 보강(권장)
  content_hash TEXT,              -- 중복 ingest 방지 및 dedup 보조
  token_count INT,                -- Phase 4 토큰 예산/조립용

  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 의미 검색(HNSW)
CREATE INDEX chunks_embedding_hnsw
ON chunks USING hnsw (embedding halfvec_cosine_ops);

-- 키워드 검색(pg_trgm 권장)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX chunks_content_trgm
ON chunks USING gin (content_text gin_trgm_ops);

-- 중복 제거(권장)
CREATE UNIQUE INDEX chunks_source_hash_uniq
ON chunks(source_id, content_hash)
WHERE content_hash IS NOT NULL;
```

### 4.2 오디오 청크: `audio_chunks` (권장)
v3.0는 Phase 2 신호를 “실제 오디오 청크”에 안정적으로 연결하기 위해 `audio_chunks`를 표준 테이블로 둔다.

```sql
CREATE TABLE audio_chunks (
  chunk_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  chunk_index INT NOT NULL,
  gcs_chunk_url TEXT NOT NULL,
  start_offset_sec FLOAT NOT NULL DEFAULT 0,   -- 원본 오디오 기준 시작 시간(초)
  duration_sec FLOAT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(session_id, chunk_index)
);

CREATE INDEX audio_chunks_session_timeline
ON audio_chunks(session_id, chunk_index);
```

### 4.3 오디오 신호: `signals` (Phase 2)
Phase 2의 산출물이며, 판단(Verdict) 없이 정보(Content)와 검색 의도(Search Queries)만 저장한다. [file:1]

```sql
CREATE TABLE signals (
  signal_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,

  -- (중요) 신호는 반드시 오디오 청크에 귀속된다(UX/감사/재생)
  audio_chunk_id UUID NOT NULL REFERENCES audio_chunks(chunk_id) ON DELETE CASCADE,

  chunk_index INT,                    -- 타임라인 정렬 보조
  content TEXT NOT NULL,
  search_queries TEXT[] DEFAULT '{}',

  t0_sec FLOAT, t1_sec FLOAT,         -- audio_chunk 내부 상대시간(초)
  signal_type TEXT,                   -- hint, trap, likely (예비 분류)
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX signals_session_timeline
ON signals(session_id, chunk_index, t0_sec);

CREATE INDEX signals_audio_chunk_idx
ON signals(audio_chunk_id);
```

### 4.4 근거 후보: `evidence_candidates` (Phase 3)
Phase 4에게 제공할 “참고 문헌 후보” 보관소다. [file:1]  
중복 저장을 허용하며, 어떤 신호에서 어떤 후보가 나왔는지 추적 가능해야 한다.

```sql
CREATE TABLE evidence_candidates (
  candidate_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- FK 고정(세션 삭제 시 후보도 정리)
  session_id UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,

  -- (중요) 어떤 signal에서 왔는지 추적
  signal_id UUID REFERENCES signals(signal_id) ON DELETE CASCADE,

  -- 수집된 교재 청크 링크
  chunk_id UUID NOT NULL REFERENCES chunks(chunk_id),

  -- 검색 메타데이터(Phase 4의 근거 강도 판단에 사용)
  query_used TEXT,
  retrieval_channel TEXT CHECK (retrieval_channel IN ('vector','keyword','rrf')),

  rank_vector INT,
  rank_keyword INT,

  score_vector FLOAT,
  score_keyword FLOAT,
  rrf_score FLOAT,

  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX evidence_candidates_session_chunk
ON evidence_candidates(session_id, chunk_id);

CREATE INDEX evidence_candidates_session_signal
ON evidence_candidates(session_id, signal_id);

CREATE INDEX evidence_candidates_session_rrf
ON evidence_candidates(session_id, rrf_score DESC);
```

---

## 오디오 타임코드 규칙(SSOT)
- `signals.t0_sec`, `signals.t1_sec`는 **audio_chunk 내부 상대시간(초)**이다.
- 원본 오디오 기준 절대시간은 `audio_chunks.start_offset_sec + signals.t0_sec`로 계산한다.
- UI/리플레이/내보내기 표준 참조는 `(audio_chunk_id, t0_sec, t1_sec)`이며, 필요 시 절대시간을 파생한다.

---

## 5. 상세 파이프라인(The Map-Reduce Workflow)
### Phase 1: Intelligent PDF Ingest (Knowledge Base)
“교재를 읽고 구조화하여 기억하는 단계”다. [file:1]

1. Router: PDF 첫 3페이지 텍스트 밀도 분석 → `Digital` vs `Scanned` 자동 분류. [file:1]
2. Visual OCR(Scanned):
   - 20페이지 단위로 sub-PDF 분할 후 Vision 모델로 전사(수식 LaTeX, 표 Markdown). [file:1]
3. Embedding:
   - `text-embedding-004`로 벡터화하여 `chunks.embedding (halfvec)`에 저장한다. [file:1]

### Phase 2: Audio Analysis (Mapper)
“강의를 듣고 시험 정보와 검색 의도를 추출하는 단계”다. [file:1]

- Input: 세션 오디오 → (권장) `audio_chunks` 단위 처리.
- Output: `signals`에 아래 필드를 저장한다. [file:1]
  - `content`: 신호 내용(시험 예고/강조/예외/함정 포인트)
  - `search_queries[]`: 교재 검증을 위한 검색어
  - `audio_chunk_id`, `t0_sec`, `t1_sec`
  - `signal_type`: 예비 분류(최종 분류는 Phase 4)

### Phase 3: Reference Gathering (Gatherer)
“최종 AI가 참고할 교재 페이지를 긁어모으는 단계”다. [file:1]

1. `signals.search_queries`를 로드한다. [file:1]
2. Hybrid Search:
   - 의미 검색: `pgvector`(halfvec + HNSW)
   - 키워드 검색: `pg_trgm` 기반 trigram similarity(키워드 채널은 trigram 유사도/랭킹을 사용한다).
   - 결합: RRF로 상위 K를 산출한다. [file:1]
3. Candidate Collection:
   - 검색 결과를 `evidence_candidates`에 **일단 다 저장**한다(Recall 우선). [file:1]
   - 이때 `session_id`뿐 아니라 반드시 `signal_id`도 저장해 “어떤 신호가 어떤 후보를 만들었는지” 추적 가능하게 한다.

### Phase 4: Global Reasoning (Reducer)
“모든 정보를 통합하여 최종 결론을 내리는 단계”다. [file:1]

#### 5.4.1 Context Assembly (입력 조립 규칙)
Signals는 세션 전체를 시간순으로 정렬한다. [file:1]  
References는 `evidence_candidates`에서 `chunk_id` 기준으로 dedup하되, 단순 텍스트 뭉치로 합치지 않고 **메타 포함 블록**으로 입력에 포함한다(식별자 유실 방지).

- 입력 블록 포맷(권장):
  - `[[CHUNK chunk_id=... source_id=... page=45-47 anchor=Chapter2/Gauss]]`
  - (다음 줄부터) `chunks.content_text`

#### 5.4.2 Grand Master Inference (Long Context)
- Input: `[강의 전체 신호 타임라인] + [메타 포함 교재 청크 블록들]` [file:1]
- System Prompt 핵심 규칙: 통합(Synthesis) + 검증(Verification) + 작성(Writing). [file:1]
- Output: `session_reports.report_json`에 professor_mentioned / likely / trap_warnings JSON 저장. [file:1]

---

## 6. Exam Report 출력 스키마(권장)
최종 리포트는 아래 3 배열을 포함한다. [file:1]

```json
{
  "professor_mentioned": [],
  "likely": [],
  "trap_warnings": []
}
```

권장 ReportItem 최소 필드(모든 카테고리 공통):
```json
{
  "title": "대표 개념/문제명",
  "why": "왜 중요한지 + 오디오 신호 요약 + 교재 근거 요약",
  "confidence": 0.0,
  "audio_refs": [
    {
      "audio_chunk_id": "uuid",
      "t0_sec": 0.0,
      "t1_sec": 0.0,
      "signal_id": "uuid"
    }
  ],
  "citations": [
    {
      "source_id": "uuid",
      "page_start": 1,
      "page_end": 2,
      "anchor_path": ["Chapter X", "Section Y"],
      "chunk_id": "uuid"
    }
  ]
}
```

Trap 확장 필드(권장):
```json
{
  "title": "함정 포인트",
  "pitfall": "오답 유도 지점",
  "why_confusing": "왜 헷갈리는지",
  "recommended_answer_style": "서술 팁(조건/예외를 어떻게 써야 하는지)",
  "correct_answer_core": "정답 핵심 한 문장",
  "audio_refs": [],
  "citations": []
}
```

---

## 7. API 명세(Internal Worker Protocol)
각 Cloud Run Worker는 HTTP POST 요청으로 트리거된다. [file:1]

- `POST /internal/pipeline/ingest`: PDF 파싱 및 적재 시작(Phase 1). [file:1]
- `POST /internal/pipeline/audio`: 오디오 분석 시작(Phase 2). [file:1]
- `POST /internal/pipeline/gather`: 근거 수집 시작(Phase 3). [file:1]
- `POST /internal/pipeline/reasoning`: 최종 리포트 생성 시작(Phase 4). [file:1]

---

## 8. 운영 규칙(상태/재시도/가드레일)
### 8.1 공통 상태 전이(권장)
- `queued → running → succeeded`
- `queued → running → failed_transient → retry → running`
- `queued → running → failed_permanent`
- `queued → running → skipped`

### 8.2 재시도 정책(권장 예시)
- Phase 2 타임아웃: 오디오 청크를 더 짧게 재분할 후 1회 재시도.
- Phase 3 근거 부족: `k_final` 또는 검색 예산을 늘리거나 쿼리 재작성 후 1회 재시도.
- Phase 4 파싱 실패: 동일 입력 1회 재호출 후 실패 처리(무한 재시도 금지).

### 8.3 Phase 4 모델 승격(선택 정책)
Reduce는 Flash-Lite로 시작하되, 아래 조건이면 상위 모델로 승격할 수 있도록 정책을 둔다. [file:1]
- 신호 수/후보 근거 토큰량이 과도하게 큼
- 근거 매핑 실패율이 비정상적으로 높음
- 과목 특성상 함정/예외 판정이 난해함

---

## 9. 개발 로드맵(Execution Plan)
- Step 1: 인프라 및 DB 구축(OCI Supabase + pgvector/halfvec + GCS 등). [file:1]
- Step 2: Phase 1 (Ingest Worker) 개발(PDF 라우팅, OCR/전사, chunking, embedding). [file:1]
- Step 3: Phase 2 (Audio Worker) 개발(신호+검색의도 추출, signals 저장). [file:1]
- Step 4: Phase 3 (Gathering Worker) 개발(hybrid search + RRF, evidence_candidates 적재). [file:1]
- Step 5: Phase 4 (Reasoning Worker) 개발(블록 입력 조립, Long Context 추론, 최종 JSON 저장). [file:1]

---

## 부록 A. Phase 4 System Prompt(권장 템플릿)
> "당신은 이 강의의 수석 조교입니다. 제공된 강의 타임라인과 교재 자료를 모두 읽고 다음을 수행하십시오.
> 1) 통합(Synthesis): 반복된 내용은 하나로 합치고 중요도를 높이십시오.
> 2) 검증(Verification): 신호(Signal)에 딱 맞는 교재 내용(Reference)을 매핑하십시오. 근거가 없으면 리포트에서 제외하십시오.
> 3) 작성(Writing): professor_mentioned, likely, trap_warnings로 분류하여 최종 JSON을 작성하십시오." [file:1]

---
```