# MVP 개선 현황 (vNext)

업데이트 기준일: 2026-02-17

## 목표

- 시험 예측 중심 리포트에서 "강의 근거 기반 교재 문제 추천 큐"로 전환
- 페이즈 간 연결 안정화(업로드 -> Map -> Retrieve -> Reduce)
- 저작권/운영 가드레일을 기본 동작으로 고정

## 완료 항목

- [x] vNext 전략 반영
  - `recommendation_queue` 출력 스키마 전환
  - 신호 타입 `hint | priority | trap | repeat` 운영
- [x] Phase 1 안정화
  - OCR 병렬 상한 도입
  - 대용량 스캔 처리 메모리 압력 완화
  - 타임아웃/배치 파라미터 운영값 반영
- [x] Phase 2 안정화
  - `audio_chunks` 중복 insert 충돌 방지(upsert)
  - 청크 처리 재시도 + 모델 호출 재시도(backoff)
  - signal 저장 idempotent 보강
- [x] Phase 3/4 연동 고정
  - Hybrid Retrieval + RRF 운영
  - Reduce에서 근거 검증/정렬/중복 제거
- [x] 업로드 UX/연결 개선
  - PDF 업로드 경로를 GCS signed URL 방식으로 일원화
  - 다중 파일 업로드 동시 처리 + 파일별 실패 격리
  - 프론트 업로드 진행률(%) 표시 추가
- [x] 저작권 방어 로직 유지
  - 원문 재출력 금지
  - 문제/해설 생성 금지
  - 근거/참조 기반 추천만 허용
- [x] 쿼터 상향 요청 접수
  - `gemini-2.5-flash-lite` `asia-southeast1` 30 RPM
  - `gemini-2.5-flash-lite` `us-central1` 30 RPM

## 현재 운영 파라미터

- `INGEST_BATCH_PAGES=1`
- `PHASE1_SCANNED_MAX_WORKERS=1000`
- `PHASE1_API_MAX_CONCURRENCY=1000`
- `PHASE1_OCR_TIMEOUT_SEC=50`
- Cloud Run Job `thunder-worker` generation `78`

## 잔여 작업 (MVP 완성 전)

- [ ] 근거 구간 클릭 -> 오디오 플레이어 타임점프
- [ ] 추천 큐 완료 체크 및 KPI 수집 이벤트 연결
- [ ] 멀티에이전트 검증 단계(Advocate/Skeptic/Judge) 추가
- [ ] 쿼터 승인 후 동시처리 상향 재튜닝(점진 적용)

## 리스크 메모

- 단일/짧은 녹음 업로드 시 근거 부족 경고가 정상 동작해야 함
- Vertex 429는 쿼터/동시성/토큰량의 복합 이슈이므로 승인 전에는 보수적 동시성 유지
