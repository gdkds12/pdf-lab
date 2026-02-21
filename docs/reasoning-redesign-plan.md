# PDF-LAB Reasoning Redesign Plan (v1)

## 1) 배경 문제
- 현재 Phase4는 대용량 컨텍스트를 단일 추론으로 처리해 지연/불안정이 발생.
- `recommendation_queue`가 0건으로 끝나는 빈도가 높음.
- Phase4 실행 시 세션별 Retrieval(Phase3) 재실행이 잦아 전체 지연이 커짐.

## 2) 목표 / 비목표
### 목표
1. 인간형 단계 추론 도입: 관찰 → 정렬 → 후보 → 검증 → 결정
2. 0건 방지: `confirmed`/`candidates` 2레벨 출력
3. Phase2 기존 신호 구조 호환 유지
4. Phase1 OCR 기반 목차(Toc) 활용

### 비목표 (1차)
- Phase2 스키마 대규모 변경
- DB 대규모 마이그레이션 강행

## 3) 신규 단계형 파이프라인

## 3.1 Stage A: Fact Pack (관찰)
입력:
- signals(Phase2)
- evidence_candidates(Phase3)
- chunks(Phase1)
- subject meta

출력:
- `fact_pack`
  - `toc_sections[]` (OCR 기반 목차 추정)
  - `signal_timeline[]` (시그널 타임라인)
  - `chunk_summaries[]` (청크 요약/페이지)
  - `data_quality` (결손/품질)

## 3.2 Stage B: Alignment Pack (정렬)
입력: fact_pack
출력: `alignment_pack`
- signal_id별 예상 페이지 범위(`pred_page_start/end`)
- `alignment_confidence` (0~1)
- 근거 사유(`reasons[]`)

규칙:
- 신호 없음 세션은 정렬 생략
- 고신뢰/중신뢰/저신뢰 버킷 분리

## 3.3 Stage C: Candidate Pack (후보 생성)
입력: alignment_pack + chunks
출력: `candidate_pack`
- 후보 문제/예제 리스트
- 근거 청크와 시그널 연결

규칙:
- Recall 우선(너무 이른 컷오프 금지)
- 페이지 범위 내 문제 패턴 우선

## 3.4 Stage D: Validation Pack (검증/반박)
입력: candidate_pack
출력: `validation_pack`
- accepted/rejected 분리
- reject_reason 표준화 (근거부족/중복/범위불일치 등)

## 3.5 Stage E: Final Report v2 (결정)
출력:
- `recommendation_queue_confirmed[]`
- `recommendation_queue_candidates[]`
- `warnings[]`
- `metrics`

정책:
- confirmed가 0이어도 candidates는 유지
- 사용자에게 "왜 confirmed가 비었는지" 설명

## 4) 성능 전략
1. 컨텍스트 상한
- 목차 기준 top-N chunk만 모델 입력
- chunk 본문 길이 캡(예: 800~1200 chars)
- near-duplicate chunk 제거

2. Retrieval 재실행 최소화
- 세션별 signal_count=0이면 retrieval skip
- evidence가 존재하면 재실행 금지

3. 모델 전략
- 기본 추론 모델: `gemini-2.5-flash` + thinking budget
- 단계별 모델 분리 가능(관찰/정렬은 flash, 최종결정만 상위모델 옵션)

## 5) Phase2 호환 전략
- 기존 signals 구조 유지 (`signal_type`, `content`, `search_queries`, `t0/t1`, `importance`)
- Stage A에서 신호를 "학습 힌트"로 재해석
- 추후 Phase2 확장은 별도 단계에서 진행

## 6) 기존 Report 호환 레이어
- 기존 UI가 `recommendation_queue`만 기대하면:
  - 우선순위: confirmed + 후보 상위 일부를 병합한 `recommendation_queue`를 임시 제공
- 신규 UI에서는 confirmed/candidates 분리 표시

## 7) 점진 배포 / 롤백
1. Feature flag 도입
- `PHASE4_V2_ENABLED`
- `PHASE4_V2_MAX_CHUNKS`

2. Canary
- 특정 subject/session만 v2 적용
- 지표: 처리시간, 0건률, 사용자 피드백

3. 롤백
- 플래그 OFF 즉시 기존 Phase4 단일 경로 복귀

## 8) 성공 지표
- 0건 리포트 비율 감소
- Phase4 p95 지연 감소
- 추천 실행률(사용자 실제 풀이 전환) 상승
- reject reason의 해석 가능성 증가
